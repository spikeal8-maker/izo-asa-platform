"""Session-bound job HTTP only; no worker/terminal/price mutation endpoints."""
from fastapi import APIRouter, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from uuid import UUID

from ..accounts.security import AuthError
from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from ..credits.schemas import CreditError
from ..entitlements.schemas import EntitlementError
from ..media.schemas import MediaError
from .schemas import QuoteInput, QuoteView, CreateJob, CancelJob, JobView, JobList, JobError
from .service import JobService
from .catalog import JobSettings


class JobRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse({"error": {"code": "invalid_input"}}, status_code=422)
            except (AuthError, CreditError, EntitlementError, MediaError, JobError) as exc:
                return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
        return handler


def attach_jobs(app, accounts):
    policy = JobSettings()
    router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"], route_class=JobRoute,
        responses={code: {"model": AuthErrorView} for code in ("4XX", 422, 503)})

    def instance(request, mutation=False, allowed=()):
        keys = [key for key, _ in request.query_params.multi_items()]
        if len(keys) != len(set(keys)) or set(keys) - set(allowed):
            raise JobError(422, "invalid_input")
        auth = accounts(request)
        if mutation:
            same_origin(request, auth)
            if len(request.headers.getlist("content-type")) != 1 or len(request.headers.getlist("x-csrf-token")) != 1:
                raise JobError(403, "csrf_rejected")
        return JobService(auth, policy), request.cookies.get(auth.policy.cookie_name)

    @router.post("/quotes", response_model=QuoteView, status_code=201)
    def quote(data: QuoteInput, request: Request):
        service, raw = instance(request, mutation=True)
        return service.quote(raw, request.headers.get("x-csrf-token"), data)

    @router.post("", response_model=JobView, status_code=201)
    def submit(data: CreateJob, request: Request):
        service, raw = instance(request, mutation=True)
        return service.submit(raw, request.headers.get("x-csrf-token"), data)

    @router.get("", response_model=JobList)
    def list_jobs(request: Request, limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=10000)):
        service, raw = instance(request, allowed=("limit", "offset"))
        return service.list(raw, limit, offset)

    @router.get("/{job_id}", response_model=JobView)
    def get_job(job_id: UUID, request: Request):
        service, raw = instance(request)
        return service.get(raw, job_id)

    @router.post("/{job_id}/cancel", response_model=JobView)
    def cancel(job_id: UUID, data: CancelJob, request: Request):
        service, raw = instance(request, mutation=True)
        return service.cancel(raw, request.headers.get("x-csrf-token"), job_id)

    app.include_router(router)
