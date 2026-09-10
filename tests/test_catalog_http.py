"""CATALOG-001 HTTP guards with real AuthService; no network/provider secret."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from izo.accounts.security import AuthError
from izo.accounts.http_security import AuthBodyLimit
from izo.catalog.routes import attach_catalog
from izo.catalog.schemas import CatalogError
from test_catalog import catalog_env, connection, credential
from test_admin import PASSWORD, password_hash, admin_env


@pytest.fixture
def catalog_http(catalog_env):
    service, users, sessions = catalog_env
    app = FastAPI()
    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse({"error":{"code":error.code}}, status_code=error.status)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error":{"code":"invalid_input"}}, status_code=422)
    attach_catalog(app, lambda request: service.auth)
    app.add_middleware(AuthBodyLimit)
    with TestClient(app) as client:
        yield client, service, users, sessions


def headers(env, who=0):
    _, service, _, sessions = env
    return {"Cookie":service.auth.policy.cookie_name+"="+sessions[who].bearer,
            "Origin":"http://localhost:8080", "X-IZO-Request":"web",
            "X-CSRF-Token":sessions[who].view.csrf_token}


def test_model_and_connection_routes_never_return_raw_secret(catalog_http):
    client, _, _, sessions = catalog_http
    h=headers(catalog_http)
    response=client.post('/api/v1/admin/catalog/connections/openrouter-primary/draft',headers=h,
                         json=connection().model_dump(mode='json'))
    assert response.status_code==200, response.text
    data=credential(1).model_dump(mode='json'); data['current_password']=PASSWORD
    bound=client.post('/api/v1/admin/catalog/connections/openrouter-primary/credentials',headers=h,json=data)
    assert bound.status_code==200
    text=bound.text
    assert 'IZO_OPENROUTER_API_KEY' not in text and PASSWORD not in text and 'reference_fingerprint' in text
    detail=client.get('/api/v1/admin/catalog/connections/openrouter-primary',headers=h)
    assert detail.status_code==200 and detail.json()['credential'] is None
    metadata=client.get('/api/v1/admin/catalog/connections/openrouter-primary/credential',headers=h)
    assert metadata.status_code==200 and 'IZO_OPENROUTER_API_KEY' not in metadata.text


def test_raw_secret_and_arbitrary_endpoint_rejected_without_echo(catalog_http):
    client=catalog_http[0]; h=headers(catalog_http)
    payload=connection().model_dump(mode='json') | {'endpoint':'https://evil.invalid'}
    result=client.post('/api/v1/admin/catalog/connections/openrouter-primary/draft',headers=h,json=payload)
    assert result.status_code==422 and 'evil.invalid' not in result.text
    client.post('/api/v1/admin/catalog/connections/openrouter-primary/draft',headers=h,
                json=connection().model_dump(mode='json'))
    data=credential(1).model_dump(mode='json'); data['current_password']=PASSWORD; data['api_key']='DO-NOT-ECHO-SECRET'
    result=client.post('/api/v1/admin/catalog/connections/openrouter-primary/credentials',headers=h,json=data)
    assert result.status_code==422 and 'DO-NOT-ECHO-SECRET' not in result.text and PASSWORD not in result.text


@pytest.mark.parametrize('changes',[{'Origin':'https://outside.invalid'}, {'X-CSRF-Token':'wrong'},
    {'X-IZO-Request':''}, {'Sec-Fetch-Site':'cross-site'}, {'Content-Type':'text/plain'}])
def test_mutations_keep_origin_csrf_and_content_guards(catalog_http, changes):
    h={**headers(catalog_http),**changes}
    response=catalog_http[0].post('/api/v1/admin/catalog/connections/openrouter-primary/draft',
        headers=h,json=connection().model_dump(mode='json'))
    assert response.status_code in {403,415,422}


def test_ordinary_account_cannot_browse_catalog(catalog_http):
    client=catalog_http[0]
    assert client.get('/api/v1/admin/catalog/models',headers=headers(catalog_http,1)).status_code==403
    assert client.get('/api/v1/admin/catalog/providers',headers=headers(catalog_http,1)).status_code==403


def test_no_client_actor_or_state_fields(catalog_http):
    client=catalog_http[0]; h=headers(catalog_http)
    payload=connection().model_dump(mode='json') | {'actor_id':str(uuid4()), 'runtime_state':'active'}
    result=client.post('/api/v1/admin/catalog/connections/openrouter-primary/draft',headers=h,json=payload)
    assert result.status_code==422
