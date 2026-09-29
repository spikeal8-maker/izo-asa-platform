"""Current account's plan only. No public assignment or admission endpoint."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .schemas import EntitlementView, EntitlementError
from .service import EntitlementService


def attach_entitlements(app, resolve_accounts):
    router = APIRouter(prefix="/api/v1/entitlements", tags=["entitlements"])

    @app.exception_handler(EntitlementError)
    async def entitlement_error(request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status,
                            headers={"Cache-Control": "no-store"})

    @router.get("", response_model=EntitlementView)
    def own_entitlements(request: Request):
        auth = resolve_accounts(request)
        # Session and plan are read in one transaction. No client identity hints.
        with auth.engine.begin() as conn:
            account, _ = auth._session(conn, request.cookies.get(auth.policy.cookie_name))
            if request.query_params:
                raise EntitlementError(422, "unexpected_query")
            return EntitlementService(clock=auth.clock).resolve(conn, account["id"])

    app.include_router(router)
