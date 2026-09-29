"""ACCESS-001 HTTP guards with real AuthService; no mock authorization."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from izo.accounts.http_security import AuthBodyLimit
from izo.accounts.security import AuthError
from izo.access.routes import attach_access
from test_access import access_env
from test_admin import admin_env, password_hash, PASSWORD


@pytest.fixture
def access_http(access_env):
    service, users, sessions = access_env
    app = FastAPI()
    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse({"error":{"code":error.code}}, status_code=error.status)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error":{"code":"invalid_input"}}, status_code=422)
    attach_access(app, lambda request: service.auth)
    app.add_middleware(AuthBodyLimit)
    with TestClient(app) as client:
        yield client, service, users, sessions

def headers(env, who=0):
    _, service, _, sessions = env
    return {"Cookie":service.auth.policy.cookie_name+"="+sessions[who].bearer,
            "Origin":"http://localhost:8080", "X-IZO-Request":"web",
            "X-CSRF-Token":sessions[who].view.csrf_token}


def grant_path(env, target=2):
    return f"/api/v1/admin/access/subjects/{env[2][target]}/grants"


def revoke_path(env, target=2):
    return f"/api/v1/admin/access/subjects/{env[2][target]}/revocations"


def grant_data(permission="plans.write", **changes):
    return {"operation_id":str(uuid4()), "permission":permission, "scope":"global",
            "ttl_seconds":3600, "case_reference":"ACCESS-HTTP-123",
            "current_password":PASSWORD, **changes}


def revoke_data(permission="plans.write", **changes):
    return {"operation_id":str(uuid4()), "permission":permission, "scope":"global",
            "case_reference":"ACCESS-HTTP-124", "current_password":PASSWORD, **changes}

def test_access_me_subject_grant_and_revoke(access_http):
    client, service, users, sessions = access_http
    me = client.get('/api/v1/admin/access/me', headers=headers(access_http))
    assert me.status_code == 200 and 'plans.write' in me.json()['delegation_ceiling']
    subject = client.get(f'/api/v1/admin/access/subjects/{users[2]}', headers=headers(access_http))
    assert subject.status_code == 200 and subject.json()['id'] == str(users[2])
    granted = client.post(grant_path(access_http), headers=headers(access_http), json=grant_data())
    assert granted.status_code == 200 and granted.json()['permission'] == 'plans.write'
    after = client.get(f'/api/v1/admin/access/subjects/{users[2]}', headers=headers(access_http)).json()
    assert any(item['permission']=='plans.write' and item['managed'] for item in after['permissions'])
    revoked = client.post(revoke_path(access_http), headers=headers(access_http), json=revoke_data())
    assert revoked.status_code == 200 and revoked.json()['action'] == 'revoke'


@pytest.mark.parametrize('changes',[{'Origin':'https://outside.invalid'}, {'X-CSRF-Token':'wrong'},
    {'X-IZO-Request':''}, {'Sec-Fetch-Site':'cross-site'}, {'Content-Type':'text/plain'}])
def test_access_mutation_uses_shared_csrf_origin_guards(access_http, changes):
    h={**headers(access_http),**changes}
    response=access_http[0].post(grant_path(access_http),headers=h,json=grant_data())
    assert response.status_code in {403,415,422}

@pytest.mark.parametrize('field,value',[
    ('permission','root.everything'),('scope','tenant'),('ttl_seconds',True),
    ('ttl_seconds','3600'),('actor_id',str(uuid4())),('delegation_ceiling',['*'])])
def test_sensitive_body_is_strict_and_password_not_echoed(access_http, field, value):
    payload=grant_data(**{field:value})
    response=access_http[0].post(grant_path(access_http),headers=headers(access_http),json=payload)
    assert response.status_code==422 and PASSWORD not in response.text


def test_readonly_and_anonymous_cannot_read_or_mutate_access(access_http):
    client, service, users, sessions=access_http
    assert client.get('/api/v1/admin/access/me',headers=headers(access_http,1)).status_code==403
    assert client.get(f'/api/v1/admin/access/subjects/{users[2]}',headers=headers(access_http,1)).status_code==403
    assert client.post(grant_path(access_http),headers=headers(access_http,1),json=grant_data()).status_code==403
    assert client.get('/api/v1/admin/access/me').status_code==401


def test_query_and_body_are_bounded(access_http):
    client=access_http[0]
    assert client.get('/api/v1/admin/access/me?role=owner',headers=headers(access_http)).status_code==422
    h={**headers(access_http),'Content-Type':'application/json'}
    response=client.post(grant_path(access_http),headers=h,content='x'*9000)
    assert response.status_code==413 and response.json()=={'error':{'code':'request_too_large'}}
