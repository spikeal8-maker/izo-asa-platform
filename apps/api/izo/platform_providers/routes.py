"""Fixed DeepSeek staff-only routes. No public key or account selector."""
from fastapi import APIRouter, Request

from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from ..config import Settings
from ..chat.execution import FakeDeepSeekProvider
from ..chat.provider import DeepSeekProvider
from .schemas import ProviderList, ProviderView, ReplaceKey, UpdatePolicy, VerifyKey
from .service import PlatformProviderService


def attach_platform_providers(app, resolve_accounts, config: Settings):
    router = APIRouter(prefix="/api/v1/admin/providers", tags=["admin-providers"],
        responses={"4XX": {"model": AuthErrorView}})

    def context(request: Request):
        if request.query_params:
            from ..accounts.security import AuthError
            raise AuthError(422, "invalid_query")
        auth = resolve_accounts(request)
        provider = getattr(request.app.state, "platform_provider_adapter", None)
        if provider is None:
            provider = FakeDeepSeekProvider() if config.environment == "test" else DeepSeekProvider()
        return auth, PlatformProviderService(auth, provider), request.cookies.get(auth.policy.cookie_name)

    @router.get("", response_model=ProviderList)
    def list_providers(request: Request):
        _, service, raw = context(request)
        return service.list(raw)

    @router.post("/deepseek/credential", response_model=ProviderView)
    def save_key(data: ReplaceKey, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        return service.replace_key(raw, request.headers.get("x-csrf-token"), data,
            request.client.host if request.client else "unknown")

    @router.post("/deepseek/verify", response_model=ProviderView)
    def verify_key(data: VerifyKey, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        return service.verify(raw, request.headers.get("x-csrf-token"), data,
            request.client.host if request.client else "unknown")

    @router.patch("/deepseek/config", response_model=ProviderView)
    def update_config(data: UpdatePolicy, request: Request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        return service.configure(raw, request.headers.get("x-csrf-token"), data,
            request.client.host if request.client else "unknown")

    app.include_router(router)
