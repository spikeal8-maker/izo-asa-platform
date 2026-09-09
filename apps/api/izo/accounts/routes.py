"""Thin HTTP layer: trusted cookie identity, strict origins and synchronizer CSRF."""
from collections.abc import Callable
from functools import lru_cache
from contextlib import asynccontextmanager
from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

from .repository import create_auth_engine
from .schemas import AuthView, LoginInput, RegisterInput, SessionList, AuthErrorView
from .security import AuthError
from .service import AuthService
from .settings import AuthSettings
from .challenge_routes import attach_challenges


class AuthBodyLimit:
    """Bound auth request bodies before JSON parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or not scope["path"].startswith("/api/v1/auth/")
                or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 8192:
                response = JSONResponse({"error": {"code": "request_too_large"}}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def attach_accounts(app, database_config) -> Callable[[Request], AuthService]:
    creation_lock = Lock()
    @lru_cache(maxsize=1)
    def configured_service():
        policy = AuthSettings()
        policy.require_configured()
        return AuthService(create_auth_engine(database_config), policy)

    def service(request: Request) -> AuthService:
        # Tests can inject their isolated DB service, never a client-supplied value.
        instance = getattr(request.app.state, "accounts_service", None)
        if instance is not None:
            return instance
        with creation_lock:
            return configured_service()

    def bearer(request, instance):
        return request.cookies.get(instance.policy.cookie_name)

    def same_origin(request, instance):
        origins = request.headers.getlist("origin")
        if (len(origins) != 1 or origins[0] not in instance.policy.origins
                or request.headers.get("x-izo-request") != "web"
                or request.headers.get("sec-fetch-site") == "cross-site"):
            raise AuthError(403, "origin_rejected")
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise AuthError(415, "json_required")

    def issue_cookie(response, instance, receipt):
        response.set_cookie(instance.policy.cookie_name, receipt.bearer,
            httponly=True, secure=instance.policy.secure_cookie, samesite="lax",
            path="/", max_age=instance.policy.absolute_seconds)
        return receipt.view

    def clear_cookie(response, instance):
        response.delete_cookie(instance.policy.cookie_name, path="/", httponly=True,
            secure=instance.policy.secure_cookie, samesite="lax")

    @app.exception_handler(AuthError)
    async def auth_error(request, exc):
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else {}
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith("/api/v1/auth/"):
            # FastAPI's default error can contain raw input including a password.
            return JSONResponse({"error": {"code": "invalid_input"}}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    router = APIRouter(prefix="/api/v1/auth", tags=["accounts"],
        responses={status: {"model": AuthErrorView, "description": "Safe authentication error"}
                   for status in ("4XX", 422, 503)})

    @router.post("/register", response_model=AuthView, status_code=201)
    def register(data: RegisterInput, request: Request, response: Response):
        instance = service(request)
        same_origin(request, instance)
        receipt = instance.register(data, request.client.host if request.client else "unknown",
                                    request.headers.get("user-agent", ""))
        return issue_cookie(response, instance, receipt)

    @router.post("/login", response_model=AuthView)
    def login(data: LoginInput, request: Request, response: Response):
        instance = service(request)
        same_origin(request, instance)
        receipt = instance.login(data, request.client.host if request.client else "unknown",
                                 request.headers.get("user-agent", ""))
        return issue_cookie(response, instance, receipt)

    @router.get("/me", response_model=AuthView)
    def me(request: Request):
        instance = service(request)
        return instance.me(bearer(request, instance))

    @router.get("/sessions", response_model=SessionList)
    def list_sessions(request: Request):
        instance = service(request)
        return instance.list_sessions(bearer(request, instance))

    def revoke_command(request, target=None, others=False):
        instance = service(request)
        same_origin(request, instance)
        revoked_current = instance.revoke(bearer(request, instance),
            request.headers.get("x-csrf-token"), target, others)
        response = Response(status_code=204)
        if revoked_current:
            clear_cookie(response, instance)
        return response

    @router.post("/logout", status_code=204, response_class=Response)
    def logout(request: Request):
        return revoke_command(request)

    @router.post("/sessions/revoke-others", status_code=204, response_class=Response)
    def revoke_others(request: Request):
        return revoke_command(request, others=True)

    @router.delete("/sessions/{session_id}", status_code=204, response_class=Response)
    def revoke_session(session_id: UUID, request: Request):
        return revoke_command(request, target=session_id)

    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application):
            try:
                yield
            finally:
                if configured_service.cache_info().currsize:
                    configured_service().engine.dispose()
                    configured_service.cache_clear()

    app.router.lifespan_context = lifespan
    app.add_middleware(AuthBodyLimit)
    attach_challenges(router, service, same_origin, bearer, clear_cookie)
    app.include_router(router)
    return service
