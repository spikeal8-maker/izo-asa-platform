"""CATALOG-002 staff HTTP surface. No endpoint accepts raw provider secrets or arbitrary endpoints."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..accounts.http_security import same_origin
from ..accounts.schemas import AuthErrorView
from .schemas import (CapabilityDraft, CapabilityList, CapabilityView, CatalogError, ChangeReceipt,
    ConnectionDraft, ConnectionList, ConnectionView, CredentialBind, CredentialView, DisableInput,
    ProofInput, ProofView, ProviderList, PublishInput, RevokeCredential)
from .service import CatalogService


def attach_catalog(app, resolve_accounts):
    router = APIRouter(prefix="/api/v1/admin/catalog", tags=["admin-catalog"], responses={
        status: {"model": AuthErrorView, "description": "Safe catalog error"}
        for status in ("4XX", 422, 503)})

    @app.exception_handler(CatalogError)
    async def catalog_error(request, exc):
        payload = {"code": exc.code}
        if exc.fields:
            payload["fields"] = list(exc.fields)
        return JSONResponse({"error": payload}, status_code=exc.status,
                            headers={"Cache-Control": "no-store"})

    def context(request):
        auth = resolve_accounts(request)
        return auth, CatalogService(auth), request.cookies.get(auth.policy.cookie_name)

    def no_query(request):
        if request.query_params.multi_items():
            raise CatalogError(422, "invalid_query")

    def mutate(request):
        auth, service, raw = context(request)
        same_origin(request, auth)
        no_query(request)
        return service, raw, request.headers.get("x-csrf-token")

    @router.get("/providers", response_model=ProviderList)
    def providers(request: Request):
        _, service, raw = context(request); no_query(request)
        return service.providers(raw)

    @router.get("/models", response_model=CapabilityList)
    def models(request: Request):
        _, service, raw = context(request); no_query(request)
        return service.capabilities(raw)

    @router.get("/models/{capability_id}", response_model=CapabilityView)
    def model(capability_id: str, request: Request):
        _, service, raw = context(request); no_query(request)
        return service.capability(raw, capability_id)

    @router.post("/models/{capability_id}/draft", response_model=ChangeReceipt)
    def model_draft(capability_id: str, data: CapabilityDraft, request: Request):
        service, raw, csrf = mutate(request)
        return service.save_capability(raw, csrf, capability_id, data)

    @router.post("/models/{capability_id}/proof", response_model=ProofView)
    def model_proof(capability_id: str, data: ProofInput, request: Request):
        service, raw, csrf = mutate(request)
        return service.proof(raw, csrf, capability_id, data)

    @router.post("/models/{capability_id}/publish", response_model=ChangeReceipt)
    def model_publish(capability_id: str, data: PublishInput, request: Request):
        service, raw, csrf = mutate(request)
        return service.publish_capability(raw, csrf, capability_id, data)

    @router.post("/models/{capability_id}/disable", response_model=ChangeReceipt)
    def model_disable(capability_id: str, data: DisableInput, request: Request):
        service, raw, csrf = mutate(request)
        return service.disable_capability(raw, csrf, capability_id, data)

    @router.get("/connections", response_model=ConnectionList)
    def connections(request: Request):
        _, service, raw = context(request); no_query(request)
        return service.connections(raw)

    @router.get("/connections/{connection_id}", response_model=ConnectionView)
    def connection(connection_id: str, request: Request):
        _, service, raw = context(request); no_query(request)
        return service.connection(raw, connection_id)

    @router.post("/connections/{connection_id}/draft", response_model=ChangeReceipt)
    def connection_draft(connection_id: str, data: ConnectionDraft, request: Request):
        service, raw, csrf = mutate(request)
        return service.save_connection(raw, csrf, connection_id, data)

    @router.get("/connections/{connection_id}/credential", response_model=CredentialView)
    def credential_view(connection_id: str, request: Request):
        _, service, raw = context(request); no_query(request)
        return service.credential(raw, connection_id)

    @router.post("/connections/{connection_id}/credentials", response_model=CredentialView)
    def credential(connection_id: str, data: CredentialBind, request: Request):
        service, raw, csrf = mutate(request)
        return service.bind_credential(raw, csrf, connection_id, data,
            request.client.host if request.client else "unknown")

    @router.post("/connections/{connection_id}/credentials/revoke", response_model=ChangeReceipt)
    def revoke(connection_id: str, data: RevokeCredential, request: Request):
        service, raw, csrf = mutate(request)
        return service.revoke_credential(raw, csrf, connection_id, data,
            request.client.host if request.client else "unknown")

    @router.post("/connections/{connection_id}/publish", response_model=ChangeReceipt)
    def connection_publish(connection_id: str, data: PublishInput, request: Request):
        service, raw, csrf = mutate(request)
        return service.publish_connection(raw, csrf, connection_id, data)

    app.include_router(router)
