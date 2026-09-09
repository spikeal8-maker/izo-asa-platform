"""Real ASGI routes/session service; no mocked identity or privileged worker HTTP."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from izo.accounts.http_security import AuthBodyLimit
from izo.jobs.routes import attach_jobs
from test_jobs import env, create


def client_for(env, monkeypatch, *, enabled=True, user=0):
    service, _, users, *_ = env
    monkeypatch.setenv('IZO_JOBS_ENABLED', 'true' if enabled else 'false')
    app = FastAPI()
    attach_jobs(app, lambda request: service.auth)
    app.add_middleware(AuthBodyLimit)
    client = TestClient(app)
    client.cookies.set(service.auth.policy.cookie_name, users[user].bearer)
    client.headers.update({'Origin':'http://localhost:8080', 'X-IZO-Request':'web',
        'X-CSRF-Token':users[user].view.csrf_token})
    return client


def quote_body():
    return dict(capability_id='test.image.v1', prompt='private synthetic request', width=64, height=64)


def test_quote_submit_read_repeat_and_cancel(env, monkeypatch):
    with client_for(env, monkeypatch) as client:
        quote = client.post('/api/v1/jobs/quotes', json=quote_body())
        assert quote.status_code == 201 and quote.json()['test_only'] is True
        body = {'quote_id':quote.json()['id'], 'operation_id':str(uuid4())}
        result = client.post('/api/v1/jobs', json=body)
        assert result.status_code == 201
        job_id = result.json()['id']
        assert client.post('/api/v1/jobs', json=body).json()['id'] == job_id
        assert client.get('/api/v1/jobs').json()['jobs'][0]['id'] == job_id
        assert client.get('/api/v1/jobs/' + job_id).json()['status'] == 'queued'
        done = client.post('/api/v1/jobs/' + job_id + '/cancel', json={})
        assert done.status_code == 200 and done.json()['status'] == 'cancelled'
        assert not any(key in result.json() for key in ('owner_id','account_id','reservation_id','output_id','plan_snapshot','attempt_id'))


@pytest.mark.parametrize('extra', [{'owner_id':str(uuid4())},{'price':0},{'executor':'local'},
    {'provider_url':'http://internal.invalid'}, {'worker_token':'synthetic-private-value'}])
def test_untrusted_fields_never_enter_job_contract(env, monkeypatch, extra):
    with client_for(env, monkeypatch) as client:
        result = client.post('/api/v1/jobs/quotes', json=quote_body() | extra)
        assert result.status_code == 422
        assert result.json() == {'error':{'code':'invalid_input'}}
        assert 'synthetic-private-value' not in result.text


@pytest.mark.parametrize('headers', [{'Origin':'https://wrong.invalid'}, {'X-CSRF-Token':'wrong'},
    {'Sec-Fetch-Site':'cross-site'}, {'X-IZO-Request':'external'}])
def test_mutation_requires_origin_csrf_and_same_site(env, monkeypatch, headers):
    with client_for(env, monkeypatch) as client:
        response = client.post('/api/v1/jobs/quotes', json=quote_body(), headers=headers)
        assert response.status_code == 403


def test_foreign_job_and_quote_ids_are_private(env, monkeypatch):
    job, command = create(env)
    with client_for(env, monkeypatch, user=1) as client:
        assert client.get('/api/v1/jobs/' + str(job.id)).status_code == 404
        assert client.post('/api/v1/jobs/' + str(job.id) + '/cancel', json={}).status_code == 404
        assert client.post('/api/v1/jobs', json={'quote_id':str(command.quote_id),
            'operation_id':str(uuid4())}).status_code == 404
        assert client.get('/api/v1/jobs').json()['jobs'] == []


def test_revoked_or_missing_session_is_denied(env, monkeypatch):
    service, _, users, *_ = env
    with client_for(env, monkeypatch) as client:
        service.auth.revoke(users[0].bearer, users[0].view.csrf_token)
        assert client.get('/api/v1/jobs').status_code == 401
        client.cookies.clear()
        assert client.get('/api/v1/jobs').status_code == 401


def test_body_and_pagination_are_bounded(env, monkeypatch):
    with client_for(env, monkeypatch) as client:
        assert client.post('/api/v1/jobs/quotes', content=b'x'*8193,
            headers={'Content-Type':'application/json'}).status_code == 413
        for query in ('?account_id=x','?limit=20&limit=10','?limit=51','?offset=-1','?offset=10001'):
            assert client.get('/api/v1/jobs' + query).status_code == 422


def test_disabled_mode_does_not_block_own_history(env, monkeypatch):
    create(env)
    with client_for(env, monkeypatch, enabled=False) as client:
        assert client.post('/api/v1/jobs/quotes', json=quote_body()).status_code == 503
        assert len(client.get('/api/v1/jobs').json()['jobs']) == 1


@pytest.mark.parametrize('suffix', ['/claim','/finish','/settle','/succeed','/heartbeat'])
def test_worker_commands_are_not_public_routes(env, monkeypatch, suffix):
    with client_for(env, monkeypatch) as client:
        assert client.post('/api/v1/jobs/' + str(uuid4()) + suffix, json={}).status_code == 404
