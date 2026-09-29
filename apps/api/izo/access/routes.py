"""ACCESS-001 HTTP surface; every mutation uses same-origin, CSRF and fresh auth."""
from uuid import UUID
from fastapi import APIRouter, Request

from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from ..accounts.security import AuthError
from .schemas import AccessMe, AccessReceipt, AccessSubject, GrantAccessInput, RevokeAccessInput
from .service import AccessService


def attach_access(app, resolve_accounts):
    router = APIRouter(prefix="/api/v1/admin/access", tags=["admin-access"], responses={
        status: {"model": AuthErrorView, "description": "Safe access-management error"}
        for status in ("4XX", 422, 503)})

    def context(request):
        auth = resolve_accounts(request)
        return auth, AccessService(auth), request.cookies.get(auth.policy.cookie_name)

    def no_query(request):
        if request.query_params:
            raise AuthError(422, "invalid_query")

    @router.get("/me", response_model=AccessMe)
    def me(request: Request):
        _, service, raw = context(request); no_query(request)
        return service.me(raw)

    @router.get("/subjects/{account_id}", response_model=AccessSubject)
    def subject(account_id: UUID, request: Request):
        _, service, raw = context(request); no_query(request)
        return service.subject(raw, account_id)

    @router.post("/subjects/{account_id}/grants", response_model=AccessReceipt)
    def grant(account_id: UUID, data: GrantAccessInput, request: Request):
        auth, service, raw = context(request); same_origin(request, auth); no_query(request)
        return service.grant(raw, request.headers.get("x-csrf-token"), account_id, data,
            request.client.host if request.client else "unknown")

    @router.post("/subjects/{account_id}/revocations", response_model=AccessReceipt)
    def revoke(account_id: UUID, data: RevokeAccessInput, request: Request):
        auth, service, raw = context(request); same_origin(request, auth); no_query(request)
        return service.revoke(raw, request.headers.get("x-csrf-token"), account_id, data,
            request.client.host if request.client else "unknown")

    app.include_router(router)
