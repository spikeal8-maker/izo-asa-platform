"""CATALOG-002 HTTP guards with real AuthService; no network/provider secret."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from izo.accounts.security import AuthError
from izo.accounts.http_security import AuthBodyLimit
from izo.catalog.routes import attach_catalog
from test_catalog import catalog_env, connection, credential, capability, CONNECTION, CAPABILITY
from test_admin import PASSWORD, password_hash, admin_env


@pytest.fixture
def catalog_http(catalog_env):
    service, _, users, sessions = catalog_env
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


def headers(env, who=2):
    _, service, _, sessions = env
    return {"Cookie":service.auth.policy.cookie_name+"="+sessions[who].bearer,
            "Origin":"http://localhost:8080", "X-IZO-Request":"web",
            "X-CSRF-Token":sessions[who].view.csrf_token}


def test_normal_json_draft_and_credential_never_return_raw_secret(catalog_http):
    client, _, _, _ = catalog_http; h=headers(catalog_http)
    response=client.post(f'/api/v1/admin/catalog/connections/{CONNECTION}/draft',headers=h,
                         json=connection().model_dump(mode='json'))
    assert response.status_code==200, response.text
    data=credential(1).model_dump(mode='json'); data['current_password']=PASSWORD
    bound=client.post(f'/api/v1/admin/catalog/connections/{CONNECTION}/credentials',headers=h,json=data)
    assert bound.status_code==200, bound.text
    assert 'IZO_FAL_KEY' not in bound.text and PASSWORD not in bound.text and 'reference_fingerprint' in bound.text
    cap=client.post(f'/api/v1/admin/catalog/models/{CAPABILITY}/draft',headers=h,
                    json=capability().model_dump(mode='json'))
    assert cap.status_code==200, cap.text
    detail=client.get(f'/api/v1/admin/catalog/connections/{CONNECTION}',headers=h)
    assert detail.status_code==200 and detail.json()['credential'] is None


def test_raw_secret_arbitrary_endpoint_and_runtime_state_rejected_without_echo(catalog_http):
    client=catalog_http[0]; h=headers(catalog_http)
    payload=connection().model_dump(mode='json') | {'endpoint':'https://evil.invalid','runtime_state':'active'}
    result=client.post(f'/api/v1/admin/catalog/connections/{CONNECTION}/draft',headers=h,json=payload)
    assert result.status_code==422 and 'evil.invalid' not in result.text
    client.post(f'/api/v1/admin/catalog/connections/{CONNECTION}/draft',headers=h,
                json=connection().model_dump(mode='json'))
    data=credential(1).model_dump(mode='json'); data['current_password']=PASSWORD; data['api_key']='DO-NOT-ECHO-SECRET'
    result=client.post(f'/api/v1/admin/catalog/connections/{CONNECTION}/credentials',headers=h,json=data)
    assert result.status_code==422 and 'DO-NOT-ECHO-SECRET' not in result.text and PASSWORD not in result.text


@pytest.mark.parametrize('changes',[{'Origin':'https://outside.invalid'}, {'X-CSRF-Token':'wrong'},
    {'X-IZO-Request':''}, {'Sec-Fetch-Site':'cross-site'}, {'Content-Type':'text/plain'}])
def test_mutations_keep_origin_csrf_and_content_guards(catalog_http, changes):
    h={**headers(catalog_http),**changes}
    response=catalog_http[0].post(f'/api/v1/admin/catalog/connections/{CONNECTION}/draft',
        headers=h,json=connection().model_dump(mode='json'))
    assert response.status_code in {403,415,422}


def test_ordinary_account_cannot_browse_catalog(catalog_http):
    client=catalog_http[0]
    assert client.get('/api/v1/admin/catalog/models',headers=headers(catalog_http,1)).status_code==403
    assert client.get('/api/v1/admin/catalog/providers',headers=headers(catalog_http,1)).status_code==403


def test_unknown_query_is_fail_closed(catalog_http):
    result=catalog_http[0].get('/api/v1/admin/catalog/providers?surprise=1',headers=headers(catalog_http))
    assert result.status_code==422 and result.json()['error']['code']=='invalid_query'


def test_no_client_actor_or_state_fields(catalog_http):
    client=catalog_http[0]; h=headers(catalog_http)
    payload=connection().model_dump(mode='json') | {'actor_id':str(uuid4())}
    result=client.post(f'/api/v1/admin/catalog/connections/{CONNECTION}/draft',headers=h,json=payload)
    assert result.status_code==422
