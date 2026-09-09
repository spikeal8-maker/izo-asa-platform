"""Owner-only read API. No public grant/reserve/settle/release endpoints."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .schemas import CreditError, Overview
from .service import CreditService


def attach_credits(app, resolve_accounts) -> None:
    router = APIRouter(prefix="/api/v1/credits", tags=["credits"])

    @app.exception_handler(CreditError)
    async def credit_error(request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status,
                            headers={"Cache-Control": "no-store"})

    @router.get("", response_model=Overview, openapi_extra={"parameters": [
        {"name": "limit", "in": "query", "required": False,
         "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}},
        {"name": "before", "in": "query", "required": False,
         "schema": {"type": "integer", "minimum": 1, "maximum": 9000000000000}},
    ]})
    def own_credits(request: Request) -> Overview:
        auth = resolve_accounts(request)
        view = auth.me(request.cookies.get(auth.policy.cookie_name))
        pairs = request.query_params.multi_items()
        if any(key not in {"limit", "before"} for key, _ in pairs) or len({k for k, _ in pairs}) != len(pairs):
            raise CreditError(422, "invalid_pagination")
        values = dict(pairs)
        if any(len(v) > 13 or not v.isascii() or not v.isdecimal() for v in values.values()):
            raise CreditError(422, "invalid_pagination")
        limit = int(values.get("limit", "20"))
        before = int(values["before"]) if "before" in values else None
        with auth.engine.begin() as conn:
            return CreditService().overview(conn, view.account.id, limit=limit, before=before)

    app.include_router(router)
