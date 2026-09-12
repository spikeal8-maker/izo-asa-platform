"""SETTINGS-002 HTTP guards on the real AuthService-backed domain."""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from izo.accounts.http_security import AuthBodyLimit
from izo.accounts.security import AuthError
from izo.access.schemas import GrantAccessInput
from izo.settings.routes import attach_settings
from test_admin import admin_env, password_hash, PASSWORD
from test_settings import settings_env, valid_policy


def headers(env, who=2):
    _, service, _, _, sessions = env
    return {"Cookie":service.auth.policy.cookie_name+"="+sessions[who].bearer,
            "Origin":"http://localhost:8080", "X-IZO-Request":"web",
            "X-CSRF-Token":sessions[who].view.csrf_token}

@pytest.fixture
def settings_http(settings_env):
    service = settings_env[0]
    app = FastAPI()
    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return JSONResponse({"error":{"code":error.code}}, status_code=error.status)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error":{"code":"invalid_input"}}, status_code=422)
    attach_settings(app, lambda request: service.auth)
    app.add_middleware(AuthBodyLimit)
    with TestClient(app) as client:
        yield client, *settings_env


def policy_json(**changes):
    return valid_policy(**changes).model_dump(mode="json")


def publish_data(expected=0, operation=None, **changes):
    return {"operation_id":str(operation or uuid4()), "expected_revision":expected,
            "policy":policy_json(**changes), "reason":"SETTINGS HTTP reviewed change"}

def test_current_preview_publish_history_and_rollback(settings_http):
    client, service, _, _, sessions = settings_http
    current = client.get('/api/v1/admin/settings/basic', headers=headers(settings_http))
    assert current.status_code == 200 and current.json()['default_version'] == 0
    preview = client.post('/api/v1/admin/settings/basic/preview',
        headers=headers(settings_http), json={"expected_revision":0,"policy":policy_json()})
    assert preview.status_code == 200 and preview.json()['generation_enabled'] is True
    first = client.post('/api/v1/admin/settings/basic/publish',
        headers=headers(settings_http), json=publish_data())
    assert first.status_code == 200 and first.json()['default_version'] == 1
    history = client.get('/api/v1/admin/settings/basic/history?limit=10',
        headers=headers(settings_http))
    assert history.status_code == 200 and history.json()['items'][0]['active'] is True
    second = client.post('/api/v1/admin/settings/basic/publish', headers=headers(settings_http),
        json=publish_data(expected=1, active_jobs=5))
    assert second.status_code == 200 and second.json()['revision'] == 2
    rolled = client.post('/api/v1/admin/settings/basic/rollback', headers=headers(settings_http),
        json={"operation_id":str(uuid4()),"expected_revision":2,"target_revision":1,
              "reason":"restore reviewed settings"})
    assert rolled.status_code == 200 and rolled.json()['action'] == 'rollback'

def test_read_only_operator_can_preview_but_not_publish(settings_http):
    client, service, access, users, sessions = settings_http
    access.grant(sessions[0].bearer, sessions[0].view.csrf_token, users[3],
        GrantAccessInput(operation_id=uuid4(), permission="plans.read", scope="global",
            ttl_seconds=3600, case_reference="SETTINGS-READ-"+uuid4().hex,
            current_password=PASSWORD), "fixture")
    current = client.get('/api/v1/admin/settings/basic', headers=headers(settings_http,3))
    assert current.status_code == 200
    preview = client.post('/api/v1/admin/settings/basic/preview', headers=headers(settings_http,3),
        json={"expected_revision":0,"policy":policy_json()})
    assert preview.status_code == 200
    denied = client.post('/api/v1/admin/settings/basic/publish', headers=headers(settings_http,3),
        json=publish_data())
    assert denied.status_code == 403


def test_anonymous_and_unrelated_staff_are_denied(settings_http):
    client = settings_http[0]
    assert client.get('/api/v1/admin/settings/basic').status_code == 401
    assert client.get('/api/v1/admin/settings/basic', headers=headers(settings_http,1)).status_code == 403

@pytest.mark.parametrize('changes',[{'Origin':'https://outside.invalid'}, {'X-CSRF-Token':'wrong'},
    {'X-IZO-Request':''}, {'Sec-Fetch-Site':'cross-site'}, {'Content-Type':'text/plain'}])
def test_publish_uses_shared_csrf_origin_guards(settings_http, changes):
    h={**headers(settings_http),**changes}
    response=settings_http[0].post('/api/v1/admin/settings/basic/publish',
        headers=h,json=publish_data())
    assert response.status_code in {403,415,422}


def test_queries_are_fail_closed(settings_http):
    client=settings_http[0]; h=headers(settings_http)
    assert client.get('/api/v1/admin/settings/basic?role=owner',headers=h).status_code==422
    assert client.get('/api/v1/admin/settings/basic/history?limit=2&limit=3',headers=h).status_code==422
    assert client.get('/api/v1/admin/settings/basic/history?limit=0',headers=h).status_code==422
    assert client.get('/api/v1/admin/settings/basic/history?cursor=x',headers=h).status_code==422
    assert client.post('/api/v1/admin/settings/basic/preview?x=1',headers=h,
        json={"expected_revision":0,"policy":policy_json()}).status_code==422


def test_body_is_strict_and_bounded(settings_http):
    client=settings_http[0]; h=headers(settings_http)
    payload=publish_data(); payload['actor_id']=str(uuid4())
    response=client.post('/api/v1/admin/settings/basic/publish',headers=h,json=payload)
    assert response.status_code==422 and 'actor_id' not in response.text
    too_large={**h,'Content-Type':'application/json'}
    response=client.post('/api/v1/admin/settings/basic/publish',headers=too_large,content='x'*9000)
    assert response.status_code==413 and response.json()=={'error':{'code':'request_too_large'}}
