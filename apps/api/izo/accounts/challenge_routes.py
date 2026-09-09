"""AUTH-002 endpoints reuse the existing origin/session/error boundary."""
from fastapi import APIRouter, Request, Response
from .challenge_schema import EmailRequest, ProofInput, ResetInput, ChangePasswordInput, MailReceipt, EmptyInput
from .challenge_policy import ChallengeSettings
from .challenges import ChallengeService
from .schemas import AuthErrorView


def attach_challenges(parent, service, same_origin, bearer, clear_cookie):
    router = APIRouter(tags=["account-security"], responses={
        status: {"model": AuthErrorView, "description": "Safe authentication error"}
        for status in ("4XX", 422, 503)})

    def context(request):
        auth = service(request)
        same_origin(request, auth)
        policy = getattr(request.app.state, "challenge_settings", None) or ChallengeSettings()
        policy.require_enabled()
        peer = request.client.host if request.client else "unknown"
        return auth, ChallengeService(auth, policy), peer

    @router.post("/email/verification/request", response_model=MailReceipt, status_code=202)
    def request_verification(data: EmptyInput, request: Request):
        auth, security, peer = context(request)
        security.request_verification(bearer(request, auth), request.headers.get("x-csrf-token"), peer)
        return MailReceipt()

    @router.post("/email/verification/confirm", status_code=204, response_class=Response)
    def confirm_verification(data: ProofInput, request: Request):
        auth, security, peer = context(request)
        security.confirm(bearer(request, auth), request.headers.get("x-csrf-token"),
                         data.token.get_secret_value(), peer)
        return Response(status_code=204)

    @router.post("/password/forgot", response_model=MailReceipt, status_code=202)
    def request_reset(data: EmailRequest, request: Request):
        _, security, peer = context(request)
        security.request_reset(data.email, peer)
        return MailReceipt()

    @router.post("/password/reset", status_code=204, response_class=Response)
    def reset_password(data: ResetInput, request: Request):
        auth, security, peer = context(request)
        security.reset(data, peer)
        response = Response(status_code=204)
        clear_cookie(response, auth)
        return response

    @router.post("/password/change", status_code=204, response_class=Response)
    def change_password(data: ChangePasswordInput, request: Request):
        auth, security, peer = context(request)
        security.change_password(bearer(request, auth), request.headers.get("x-csrf-token"), data, peer)
        response = Response(status_code=204)
        clear_cookie(response, auth)
        return response

    parent.include_router(router)
