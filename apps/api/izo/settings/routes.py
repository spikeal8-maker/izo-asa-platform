"""A-27/AD-08 backend surface for the already-used basic plan policy."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from .schemas import (BasicSettingsView, HistoryView, PreviewInput, PreviewView,
                      PublishInput, PublishReceipt, RollbackInput, SettingsError)
from .service import SettingsService


def attach_settings(app, resolve_accounts):
    router = APIRouter(prefix="/api/v1/admin/settings", tags=["admin-settings"],
        responses={status: {"model": AuthErrorView, "description": "Safe settings error"}
                   for status in ("4XX", 422, 503)})

    @app.exception_handler(SettingsError)
    async def settings_error(request, exc):
        error = {"code": exc.code}
        if exc.fields:
            error["fields"] = list(exc.fields)
        return JSONResponse({"error": error}, status_code=exc.status,
                            headers={"Cache-Control": "no-store"})

    def context(request):
        auth = resolve_accounts(request)
        return auth, SettingsService(auth), request.cookies.get(auth.policy.cookie_name)

    @router.get("/basic", response_model=BasicSettingsView)
    def current(request: Request):
        _, service, raw = context(request)
        if request.query_params:
            raise SettingsError(422, "unexpected_query")
        return service.view(raw)

    @router.get("/basic/history", response_model=HistoryView)
    def history(request: Request, limit: int = 20):
        _, service, raw = context(request)
        return service.history(raw, limit)

    @router.post("/basic/preview", response_model=PreviewView)
    def preview(data: PreviewInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        return service.preview(raw, data)

    @router.post("/basic/publish", response_model=PublishReceipt)
    def publish(data: PublishInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        return service.publish(raw, request.headers.get("x-csrf-token"), data)

    @router.post("/basic/rollback", response_model=PublishReceipt)
    def rollback(data: RollbackInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        return service.rollback(raw, request.headers.get("x-csrf-token"), data)

    app.include_router(router)
