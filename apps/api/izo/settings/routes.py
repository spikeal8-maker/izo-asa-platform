"""SETTINGS-002 HTTP surface for the existing typed basic PlanPolicy."""
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

    def query_params(request, allowed):
        pairs = request.query_params.multi_items()
        if len(pairs) != len({key for key, _ in pairs}) or any(key not in allowed for key, _ in pairs):
            raise SettingsError(422, "invalid_query")
        return dict(pairs)

    def integer(params, key, maximum, default):
        value = params.get(key)
        if value is None:
            return default
        if len(value) > 13 or not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= maximum:
            raise SettingsError(422, "invalid_pagination")
        return int(value)

    @router.get("/basic", response_model=BasicSettingsView)
    def current(request: Request):
        _, service, raw = context(request)
        query_params(request, set())
        return service.view(raw)

    @router.get("/basic/history", response_model=HistoryView)
    def history(request: Request):
        _, service, raw = context(request)
        args = query_params(request, {"limit"})
        return service.history(raw, integer(args, "limit", 50, 20))

    @router.post("/basic/preview", response_model=PreviewView)
    def preview(data: PreviewInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth); query_params(request, set())
        return service.preview(raw, data)

    @router.post("/basic/publish", response_model=PublishReceipt)
    def publish(data: PublishInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth); query_params(request, set())
        return service.publish(raw, request.headers.get("x-csrf-token"), data)

    @router.post("/basic/rollback", response_model=PublishReceipt)
    def rollback(data: RollbackInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth); query_params(request, set())
        return service.rollback(raw, request.headers.get("x-csrf-token"), data)

    app.include_router(router)
