"""Thin same-origin Chat HTTP boundary; provider details remain private."""
from __future__ import annotations

from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse, StreamingResponse

from ..accounts.http_security import same_origin
from .credential_routes import attach_credential_routes
from .provider import DeepSeekProvider, FakeDeepSeekProvider
from .provider_openrouter import OpenRouterProvider, FakeOpenRouterProvider
from .schemas import (
    ChatPolicyView, OpenRouterCatalogView, RequestCreate, RequestView, ThreadCreate, ThreadDetail,
    ThreadList, ThreadView,
)
from .service import ChatError, ChatService
from .schemas import ChatSettings

class ChatBodyLimit:
    """Bound mutating Chat JSON before FastAPI parses it."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http"
                or not scope["path"].startswith("/api/v1/chat/")
                or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 32768:
                response = JSONResponse(
                    {"error": {"code": "request_too_large"}},
                    status_code=413)
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay, send)

def attach_chat(app, database_config, accounts_provider) -> None:
    creation_lock = Lock()
    app.add_middleware(ChatBodyLimit)

    def runtime_service(request: Request) -> ChatService:
        injected = getattr(request.app.state, "chat_service", None)
        if injected is not None:
            return injected
        with creation_lock:
            current = getattr(
                request.app.state, "_chat_runtime_service", None)
            if current is None:
                provider = (
                    FakeDeepSeekProvider()
                    if database_config.environment == "test"
                    else DeepSeekProvider()
                )
                openrouter = (
                    FakeOpenRouterProvider()
                    if database_config.environment == "test"
                    else OpenRouterProvider()
                )
                from ..media.objects import MediaStore
                current = ChatService(
                    accounts_provider(request),
                    ChatSettings(),
                    provider,
                    media_store=MediaStore(database_config),
                    environment=database_config.environment,
                    providers={"openrouter": openrouter})
                request.app.state._chat_runtime_service = current
            return current

    def bearer(request: Request, service: ChatService):
        return request.cookies.get(
            service.auth.policy.cookie_name)

    def mutation(
            request: Request,
            service: ChatService) -> tuple[str | None, str | None]:
        same_origin(request, service.auth)
        return (
            bearer(request, service),
            request.headers.get("x-csrf-token"),
        )

    @app.exception_handler(ChatError)
    async def chat_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code}},
            status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(request, exc):
        if request.url.path.startswith(
                ("/api/v1/auth/", "/api/v1/admin/", "/api/v1/chat/")):
            return JSONResponse(
                {"error": {"code": "invalid_input"}},
                status_code=422)
        return await request_validation_exception_handler(
            request, exc)

    @app.post("/api/v1/auth/local-preview", include_in_schema=False)
    def local_preview(request: Request, response: Response):
        service = runtime_service(request)
        if not service.policy.local_preview_enabled:
            raise ChatError(404, "not_found")
        if database_config.environment not in {"development", "test"}:
            raise ChatError(403, "local_preview_forbidden")
        same_origin(request, service.auth)
        receipt = service.local_preview_session(
            request.headers.get("user-agent", "Local preview"))
        policy = service.auth.policy
        response.set_cookie(policy.cookie_name, receipt.bearer, httponly=True,
            secure=policy.secure_cookie, samesite="lax", path="/",
            max_age=policy.absolute_seconds)
        return receipt.view

    router = APIRouter(
        prefix="/api/v1/chat", tags=["chat"])

    @router.get(
        "/policy", response_model=ChatPolicyView)
    def policy(request: Request):
        service = runtime_service(request)
        return service.public_policy(
            bearer(request, service))

    attach_credential_routes(
        router, runtime_service, bearer, mutation)

    @router.get(
        "/catalog/openrouter", response_model=OpenRouterCatalogView)
    def openrouter_catalog(request: Request):
        service = runtime_service(request)
        return service.openrouter_catalog(
            bearer(request, service))

    @router.get(
        "/threads", response_model=ThreadList)
    def threads(request: Request):
        service = runtime_service(request)
        return service.list_threads(
            bearer(request, service))

    @router.post(
        "/threads",
        response_model=ThreadView,
        status_code=201)
    def create_thread(
            data: ThreadCreate, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.create_thread(
            raw, csrf, data.title)

    @router.get(
        "/threads/{thread_id}",
        response_model=ThreadDetail)
    def thread(thread_id: UUID, request: Request):
        service = runtime_service(request)
        return service.thread_detail(
            bearer(request, service),
            thread_id)

    @router.post(
        "/threads/{thread_id}/requests",
        response_model=RequestView,
        status_code=202)
    def create_request(
            thread_id: UUID,
            data: RequestCreate,
            request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.create_request(
            raw, csrf, thread_id, data)

    @router.get(
        "/requests/{request_id}",
        response_model=RequestView)
    def get_request(
            request_id: UUID, request: Request):
        service = runtime_service(request)
        return service.request(
            bearer(request, service),
            request_id)

    @router.post(
        "/requests/{request_id}/stop",
        response_model=RequestView)
    def stop_request(
            request_id: UUID, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.stop(
            raw, csrf, request_id)

    @router.get(
        "/requests/{request_id}/events")
    def events(
            request_id: UUID, request: Request):
        service = runtime_service(request)
        stream = service.stream_events(
            bearer(request, service),
            request_id)
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff",
            })

    app.include_router(router)
