"""Staff HTTP through real AuthService on SQLite; real browser/PG is separate CI."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from izo.accounts.security import AuthError
from izo.accounts.http_security import AuthBodyLimit
from izo.credits.routes import attach_credits
from izo.admin.routes import attach_admin
from test_admin import admin_env, password_hash, PASSWORD


@pytest.fixture
def admin_http(admin_env):
    service, users, sessions = admin_env
    app = FastAPI()
    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse({"error":{"code":error.code}}, status_code=error.status)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error":{"code":"invalid_input"}}, status_code=422)
    attach_credits(app, lambda request: service.auth)
    attach_admin(app, lambda request: service.auth)
    app.add_middleware(AuthBodyLimit)
    with TestClient(app) as client:
        yield client, service, users, sessions


def headers(env, who=0):
    _, service, _, sessions = env
    return {"Cookie":service.auth.policy.cookie_name+"="+sessions[who].bearer,
            "Origin":"http://localhost:8080", "X-IZO-Request":"web",
            "X-CSRF-Token":sessions[who].view.csrf_token}


def grant_path(env):
    return '/api/v1/admin/users/'+str(env[2][2])+'/compensations'


def data(**kwargs):
    return {"operation_id":str(uuid4()), "amount":50, "case_reference":"HTTP-123",
            "current_password":PASSWORD, **kwargs}


def test_real_http_grant_then_own_balance(admin_http):
    client, service, users, sessions = admin_http
    payload=data()
    response=client.post(grant_path(admin_http), headers=headers(admin_http), json=payload)
    assert response.status_code==200
    assert response.json()['entry']['balance_after']==50
    assert client.post(grant_path(admin_http),headers=headers(admin_http),json=payload).json()==response.json()
    own=client.get('/api/v1/credits',headers=headers(admin_http,2))
    assert own.status_code==200 and own.json()['balance']['available']==50
    assert client.get('/api/v1/admin/users/'+str(users[3]), headers=headers(admin_http,2)).status_code==403


@pytest.mark.parametrize('query',['actor=forged','limit=0','limit=1000','q=recipient&q=other',
                                 'limit=1.0','limit=-1','after=invalid','role=admin'])
def test_queries_cannot_bypass_limits(admin_http,query):
    client=admin_http[0]
    response=client.get('/api/v1/admin/users?q=Recipient&'+query,headers=headers(admin_http))
    assert response.status_code==422


@pytest.mark.parametrize('field,value',[('role','admin'),('grant_limit',1000),('amount',True),
    ('amount',-50),('amount','50'),('actor_id',str(uuid4()))])
def test_malformed_sensitive_body_is_redacted(admin_http,field,value):
    client=admin_http[0]
    response=client.post(grant_path(admin_http),headers=headers(admin_http),json=data(**{field:value}))
    assert response.status_code==422
    assert PASSWORD not in response.text


@pytest.mark.parametrize('changes',[{'Origin':'https://outside.invalid'}, {'X-CSRF-Token':'wrong'},
    {'X-IZO-Request':''}, {'Sec-Fetch-Site':'cross-site'}, {'Content-Type':'text/plain'}])
def test_csrf_origin_and_content_guards(admin_http,changes):
    client=admin_http[0]
    h={**headers(admin_http),**changes}
    assert client.post(grant_path(admin_http),headers=h,json=data()).status_code in {403,415,422}


def test_body_bounded_before_parser(admin_http):
    client=admin_http[0]
    h={**headers(admin_http),'Content-Type':'application/json'}
    response=client.post(grant_path(admin_http),headers=h,content='x'*9000)
    assert response.status_code==413
    assert response.json()=={'error':{'code':'request_too_large'}}


@pytest.mark.parametrize('suffix',['/me','/users?q=Recipient','/audit'])
def test_anonymous_rejected(admin_http,suffix):
    assert admin_http[0].get('/api/v1/admin'+suffix).status_code==401


def test_readonly_metadata_never_prefetches_balance(admin_http):
    client,service,users,sessions=admin_http
    result=client.get('/api/v1/admin/users/'+str(users[2]),headers=headers(admin_http,1))
    assert result.status_code==200
    assert not {'email','permissions','balance','password_hash','sessions'} & result.json().keys()
    assert client.get('/api/v1/admin/users/'+str(users[2])+'/credits',headers=headers(admin_http,1)).status_code==403


def test_malformed_uuid_does_not_echo_password(admin_http):
    response=admin_http[0].post('/api/v1/admin/users/not-a-uuid/compensations',
        headers=headers(admin_http), json=data())
    assert response.status_code==422 and PASSWORD not in response.text
