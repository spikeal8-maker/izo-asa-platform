"""Narrow guest HTTP surface: one test image, result read and same-owner claim."""
from functools import lru_cache
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse

from ..accounts.guest_schemas import GuestStart, GuestView
from ..accounts.guest_service import GuestService
from ..accounts.guest_settings import GuestSettings
from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView, AuthView, RegisterInput
from ..accounts.security import AuthError
from ..credits.schemas import CreditError
from ..credits.trial import seed_guest_trial
from ..entitlements.policy import ImageDemand, ImageSize, RuntimeState, UsageSnapshot
from ..entitlements.schemas import EntitlementError
from ..entitlements.service import EntitlementService
from ..jobs import tables as job_tables
from ..jobs.catalog import JobSettings, TEST_CAPABILITY, capability, output_bound
from ..jobs.schemas import ACTIVE, CreateJob, JobError, JobList, JobView, QuoteInput, QuoteView
from ..jobs.service import JobService
from ..media.objects import MediaStore
from ..media.schemas import AssetView, MediaError
from ..media.service import MediaService
from .media import read_owned


class GuestRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse({"error": {"code": "invalid_input"}}, status_code=422)
            except (AuthError, CreditError, EntitlementError, MediaError, JobError) as exc:
                headers = {"Retry-After": str(exc.retry_after)} if getattr(exc, "retry_after", None) else {}
                return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status, headers=headers)
        return handler


def attach_guest(app, accounts, config):
    settings = GuestSettings()
    jobs_policy = JobSettings()

    @lru_cache(maxsize=1)
    def store():
        return MediaStore(config)

    def services(request):
        auth = accounts(request)
        guest = GuestService(auth, settings)
        objects = getattr(request.app.state, "media_store", None)
        media = MediaService(guest, objects if objects is not None else store())
        return auth, guest, media

    def raw(request, auth):
        return request.cookies.get(settings.cookie_name(auth.policy.secure_cookie))

    def mutation(request, auth):
        same_origin(request, auth)
        if len(request.headers.getlist("content-type")) != 1:
            raise AuthError(403, "csrf_rejected")

    def require_trial_draft(draft):
        if draft.capability_id != TEST_CAPABILITY:
            raise AuthError(403, "guest_capability_restricted")
        if draft.width != settings.trial_width or draft.height != settings.trial_height:
            raise AuthError(403, "guest_size_restricted")

    def initialize_trial(auth):
        def initialize(conn, account_id, now):
            seed_guest_trial(conn, account_id, settings.trial_credits, now)
            plans = EntitlementService(clock=lambda: now)
            try:
                view = plans.resolve(conn, account_id)
                if not view.configured or view.policy is None:
                    raise AuthError(503, "guest_trial_unavailable")
                spec = capability(TEST_CAPABILITY)
                demand = ImageDemand(capability_id=TEST_CAPABILITY, executor="api",
                    size=ImageSize(width=settings.trial_width, height=settings.trial_height),
                    input_count=0, largest_input_bytes=0,
                    output_bytes_bound=output_bound(settings.trial_width, settings.trial_height),
                    reserve_credits=spec.credits)
                usage = UsageSnapshot(account_id=account_id, as_of=view.as_of,
                    window_seconds=view.policy.window_seconds, active_jobs=0, submissions=0,
                    committed_bytes=0, reserved_bytes=0)
                decision = plans.assess_image(conn, account_id, demand,
                    RuntimeState(feature_enabled=jobs_policy.enabled,
                        capability_supported=True, provider_available=True), usage)
            except EntitlementError as exc:
                raise AuthError(503, "guest_trial_unavailable") from exc
            if not decision.allowed:
                raise AuthError(503, "guest_trial_unavailable")
        return initialize

    def set_guest_cookie(response, auth, receipt):
        response.set_cookie(settings.cookie_name(auth.policy.secure_cookie), receipt.bearer,
            httponly=True, secure=auth.policy.secure_cookie, samesite="lax", path="/",
            max_age=settings.session_seconds)

    def clear_guest_cookie(response, auth):
        response.delete_cookie(settings.cookie_name(auth.policy.secure_cookie), path="/",
            httponly=True, secure=auth.policy.secure_cookie, samesite="lax")

    def claim_guard(conn, account_id):
        active = conn.execute(sa.select(job_tables.jobs.c.id).where(
            job_tables.jobs.c.account_id == account_id,
            job_tables.jobs.c.status.in_(ACTIVE)).limit(1)).first()
        if active is not None:
            raise AuthError(409, "guest_job_active")

    router = APIRouter(prefix="/api/v1/guest", tags=["guest"], route_class=GuestRoute,
        responses={code: {"model": AuthErrorView} for code in ("4XX", 422, 503)})

    @router.post("/start", response_model=GuestView, status_code=201)
    def start(_: GuestStart, request: Request, response: Response):
        auth, guest, _ = services(request)
        mutation(request, auth)
        receipt = guest.start(request.client.host if request.client else "unknown",
            request.headers.get("user-agent", ""), raw(request, auth),
            initializer=initialize_trial(auth))
        set_guest_cookie(response, auth, receipt)
        return receipt.view

    @router.get("/me", response_model=GuestView)
    def me(request: Request):
        auth, guest, _ = services(request)
        return guest.me(raw(request, auth))

    @router.post("/quotes", response_model=QuoteView, status_code=201)
    def quote(data: QuoteInput, request: Request):
        auth, guest, _ = services(request)
        mutation(request, auth)
        require_trial_draft(data)
        return JobService(guest, jobs_policy).quote(
            raw(request, auth), request.headers.get("x-csrf-token"), data)

    @router.post("/jobs", response_model=JobView, status_code=201)
    def submit(data: CreateJob, request: Request):
        auth, guest, _ = services(request)
        mutation(request, auth)

        def admission_guard(conn, principal, command, draft):
            require_trial_draft(draft)
            guest.admission_guard(conn, principal, command, draft)

        return JobService(guest, jobs_policy, admission_guard=admission_guard).submit(
            raw(request, auth), request.headers.get("x-csrf-token"), data)

    @router.get("/jobs", response_model=JobList)
    def list_jobs(request: Request):
        auth, guest, _ = services(request)
        return JobService(guest, jobs_policy).list(raw(request, auth), limit=5, offset=0)

    @router.get("/jobs/{job_id}", response_model=JobView)
    def get_job(job_id: UUID, request: Request):
        auth, guest, _ = services(request)
        return JobService(guest, jobs_policy).get(raw(request, auth), job_id)

    @router.get("/assets/{asset_id}", response_model=AssetView)
    def asset(asset_id: UUID, request: Request):
        auth, _, media = services(request)
        return media.get(raw(request, auth), asset_id)

    @router.get("/assets/{asset_id}/content", response_class=Response,
                responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}})
    def content(asset_id: UUID, request: Request):
        auth, guest, media = services(request)
        data = read_owned(guest, media.store, raw(request, auth), asset_id)
        return Response(data, media_type="image/png", headers={
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox", "Referrer-Policy": "no-referrer"})

    @router.post("/claim", response_model=AuthView, status_code=201)
    def claim(data: RegisterInput, request: Request, response: Response):
        auth, guest, _ = services(request)
        mutation(request, auth)
        receipt = guest.claim(raw(request, auth), request.headers.get("x-csrf-token"), data,
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", ""), guard=claim_guard)
        response.set_cookie(auth.policy.cookie_name, receipt.bearer, httponly=True,
            secure=auth.policy.secure_cookie, samesite="lax", path="/",
            max_age=auth.policy.absolute_seconds)
        clear_guest_cookie(response, auth)
        return receipt.view

    app.include_router(router)
