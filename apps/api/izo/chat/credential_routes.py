"""Provider-qualified Chat credential HTTP routes."""
from fastapi import Request

from .schemas import (
    CredentialCommand, CredentialListView, CredentialView,
    CredentialWrite, ProviderId,
)


def attach_credential_routes(router, runtime_service, bearer, mutation):
    @router.get("/credentials", response_model=CredentialListView)
    def credentials(request: Request):
        service = runtime_service(request)
        return service.credentials(bearer(request, service))

    @router.get("/credentials/{provider}", response_model=CredentialView)
    def provider_credential(provider: ProviderId, request: Request):
        service = runtime_service(request)
        return service.credential(bearer(request, service), provider)

    @router.post("/credentials/{provider}", response_model=CredentialView)
    def save_provider_credential(
            provider: ProviderId, data: CredentialWrite, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.save_credential(raw, csrf, data, provider)

    @router.post(
        "/credentials/{provider}/verify", response_model=CredentialView)
    def verify_provider_credential(
            provider: ProviderId, data: CredentialCommand, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.verify_credential(raw, csrf, data, provider)

    @router.post(
        "/credentials/{provider}/disable", response_model=CredentialView)
    def disable_provider_credential(
            provider: ProviderId, data: CredentialCommand, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.disable_credential(raw, csrf, data, provider)

    @router.get("/credential", response_model=CredentialView)
    def credential(request: Request):
        service = runtime_service(request)
        return service.credential(bearer(request, service))

    @router.post("/credential", response_model=CredentialView)
    def save_credential(data: CredentialWrite, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.save_credential(raw, csrf, data)

    @router.post("/credential/verify", response_model=CredentialView)
    def verify_credential(data: CredentialCommand, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.verify_credential(raw, csrf, data)

    @router.post("/credential/disable", response_model=CredentialView)
    def disable_credential(data: CredentialCommand, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return service.disable_credential(raw, csrf, data)
