"""Staff catalog HTTP boundary: same-origin mutation and server-side grants."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from ..accounts.security import AuthError
from .schemas import CatalogPatch, CatalogView
from .service import CatalogError, CatalogService


def attach_catalog(app, resolve_accounts):
    router = APIRouter(prefix="/api/v1/admin/catalog", tags=["admin-catalog"],
        responses={status: {"model": AuthErrorView, "description": "Safe catalog error"}
                   for status in ("4XX", 422, 503)})

    @app.exception_handler(CatalogError)
    async def catalog_error(request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)

    def context(request):
        auth = resolve_accounts(request)
        return auth, CatalogService(auth), request.cookies.get(auth.policy.cookie_name)

    def no_query(request):
        if request.query_params:
            raise AuthError(422, "invalid_query")

    @router.get("", response_model=CatalogView)
    def read(request: Request):
        _, service, raw = context(request)
        no_query(request)
        return service.read(raw)

    @router.patch("/models/{model_id}", response_model=CatalogView)
    def patch(model_id: str, command: CatalogPatch, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        no_query(request)
        return service.patch(raw, request.headers.get("x-csrf-token"), model_id, command)

    app.include_router(router)
