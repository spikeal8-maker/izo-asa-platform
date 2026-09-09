"""Staff HTTP surface. No caller-supplied actor, permissions, cap or ledger rewrite."""
from uuid import UUID
from fastapi import APIRouter, Request
from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from ..accounts.security import AuthError
from ..credits.schemas import Overview
from .service import AdminService
from .schemas import (AdminAccess, AdminUsers, AdminUser, AdminEvents,
                      CompensationInput, CompensationReceipt)


def query_params(request, allowed):
    pairs = request.query_params.multi_items()
    if len(pairs) != len({key for key, _ in pairs}) or any(key not in allowed for key, _ in pairs):
        raise AuthError(422, "invalid_query")
    return dict(pairs)


def integer(params, key, maximum, default=None):
    value = params.get(key)
    if value is None:
        return default
    if len(value) > 13 or not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= maximum:
        raise AuthError(422, "invalid_pagination")
    return int(value)


def cursor(params, key):
    if key not in params:
        return None
    try:
        return UUID(params[key])
    except ValueError:
        raise AuthError(422, "invalid_pagination") from None


def attach_admin(app, resolve_accounts):
    router = APIRouter(prefix="/api/v1/admin", tags=["admin"], responses={
        status: {"model": AuthErrorView, "description": "Safe staff error"}
        for status in ("4XX", 422, 503)})

    def context(request):
        auth = resolve_accounts(request)
        return auth, AdminService(auth), request.cookies.get(auth.policy.cookie_name)

    @router.get("/me", response_model=AdminAccess)
    def me(request: Request):
        _, service, raw = context(request)
        query_params(request, set())
        return service.me(raw)

    @router.get("/users", response_model=AdminUsers)
    def users(request: Request):
        _, service, raw = context(request)
        args = query_params(request, {"q", "limit", "after"})
        return service.users(raw, args.get("q", ""), integer(args, "limit", 50, 20), cursor(args, "after"))

    @router.get("/users/{account_id}", response_model=AdminUser)
    def user(account_id: UUID, request: Request):
        _, service, raw = context(request)
        query_params(request, set())
        return service.user(raw, account_id)

    @router.get("/users/{account_id}/credits", response_model=Overview)
    def credits(account_id: UUID, request: Request):
        _, service, raw = context(request)
        args = query_params(request, {"limit", "before"})
        return service.credits_view(raw, account_id, integer(args, "limit", 100, 20),
                                    integer(args, "before", 9_000_000_000_000))

    @router.post("/users/{account_id}/compensations", response_model=CompensationReceipt)
    def compensate(account_id: UUID, data: CompensationInput, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        query_params(request, set())
        return service.compensate(raw, request.headers.get("x-csrf-token"), account_id,
            data, request.client.host if request.client else "unknown")

    @router.get("/audit", response_model=AdminEvents)
    def audit(request: Request):
        _, service, raw = context(request)
        args = query_params(request, {"limit", "before"})
        return service.audit(raw, integer(args, "limit", 50, 20), cursor(args, "before"))

    app.include_router(router)
