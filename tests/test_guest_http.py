"""GUEST-001 HTTP boundary: isolated cookie, strict mutation guards and result claim."""
from uuid import uuid4

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from izo.accounts import tables as account_tables
from izo.accounts.http_security import AuthBodyLimit
from izo.credits import tables as credit_tables
from izo.guest.routes import attach_guest
from test_guest import guest_env


def client_for(env, monkeypatch, trial_size=64):
    auth, _, _, _, _, _, store = env
    monkeypatch.setenv('IZO_GUEST_ENABLED', 'true')
    monkeypatch.setenv('IZO_GUEST_TRIAL_CREDITS', '3')
    monkeypatch.setenv('IZO_GUEST_NETWORK_LIMIT', '10')
    monkeypatch.setenv('IZO_GUEST_RATE_WINDOW', '3600')
    monkeypatch.setenv('IZO_GUEST_TRIAL_WIDTH', str(trial_size))
    monkeypatch.setenv('IZO_GUEST_TRIAL_HEIGHT', str(trial_size))
    monkeypatch.setenv('IZO_JOBS_ENABLED', 'true')
    app = FastAPI()
    app.state.media_store = store
    attach_guest(app, lambda request: auth, object())
    app.add_middleware(AuthBodyLimit)
    client = TestClient(app)
    client.headers.update({'Origin': 'http://localhost:8080', 'X-IZO-Request': 'web'})
    return client


def start(client):
    response = client.post('/api/v1/guest/start', json={})
    assert response.status_code == 201
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return response.json()


def quote(client, **extra):
    return client.post('/api/v1/guest/quotes', json={
        'capability_id': 'test.image.v1', 'prompt': 'guest http trial',
        'width': 64, 'height': 64, **extra})


def test_guest_start_quote_submit_recovery_and_second_job_limit(guest_env, monkeypatch):
    with client_for(guest_env, monkeypatch) as client:
        first = start(client)
        repeated = client.post('/api/v1/guest/start', json={})
        assert repeated.status_code == 201 and repeated.json()['account_id'] == first['account_id']
        assert client.get('/api/v1/guest/me').json()['account_id'] == first['account_id']
        priced = quote(client)
        assert priced.status_code == 201 and priced.json()['credits'] == 1
        body = {'quote_id': priced.json()['id'], 'operation_id': str(uuid4())}
        job = client.post('/api/v1/guest/jobs', json=body)
        assert job.status_code == 201
        assert client.post('/api/v1/guest/jobs', json=body).json()['id'] == job.json()['id']
        history = client.get('/api/v1/guest/jobs')
        assert history.status_code == 200 and [item['id'] for item in history.json()['jobs']] == [job.json()['id']]
        next_quote = quote(client)
        blocked = client.post('/api/v1/guest/jobs', json={
            'quote_id': next_quote.json()['id'], 'operation_id': str(uuid4())})
        assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'guest_trial_used'


def test_guest_mutations_fail_closed_and_external_capability_is_forbidden(guest_env, monkeypatch):
    with client_for(guest_env, monkeypatch) as client:
        assert client.post('/api/v1/guest/start', json={},
            headers={'Origin': 'https://wrong.invalid'}).status_code == 403
        assert client.post('/api/v1/guest/start', content=b'x' * 8193,
            headers={'Content-Type': 'application/json'}).status_code == 413
        start(client)
        injected = quote(client, owner_id=str(uuid4()))
        assert injected.status_code == 422 and injected.json() == {'error': {'code': 'invalid_input'}}
        external = client.post('/api/v1/guest/quotes', json={
            'capability_id': 'fal.flux2.klein.4b', 'prompt': 'no paid guest call',
            'width': 64, 'height': 64})
        assert external.status_code == 403
        oversized = client.post('/api/v1/guest/quotes', json={
            'capability_id': 'test.image.v1', 'prompt': 'wrong guest size',
            'width': 128, 'height': 128})
        assert oversized.status_code == 403
        assert oversized.json()['error']['code'] == 'guest_size_restricted'
        csrf = client.headers.pop('X-CSRF-Token')
        assert quote(client).status_code == 403
        client.headers['X-CSRF-Token'] = csrf


def test_guest_start_rolls_back_when_plan_cannot_support_trial(guest_env, monkeypatch):
    auth, *_ = guest_env
    with auth.engine.begin() as conn:
        before_accounts = conn.execute(sa.select(sa.func.count()).select_from(
            account_tables.accounts)).scalar_one()
        before_trials = conn.execute(sa.select(sa.func.count()).select_from(
            credit_tables.ledger).where(credit_tables.ledger.c.kind == 'trial')).scalar_one()
    with client_for(guest_env, monkeypatch, trial_size=128) as client:
        response = client.post('/api/v1/guest/start', json={})
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'guest_trial_unavailable'
        assert client.get('/api/v1/guest/me').status_code == 401
    with auth.engine.begin() as conn:
        after_accounts = conn.execute(sa.select(sa.func.count()).select_from(
            account_tables.accounts)).scalar_one()
        after_trials = conn.execute(sa.select(sa.func.count()).select_from(
            credit_tables.ledger).where(credit_tables.ledger.c.kind == 'trial')).scalar_one()
    assert (after_accounts, after_trials) == (before_accounts, before_trials)


def test_terminal_result_can_be_read_then_claimed_by_same_account(guest_env, monkeypatch):
    auth, _, _, _, runner, _, _ = guest_env
    with client_for(guest_env, monkeypatch) as client:
        guest = start(client)
        priced = quote(client).json()
        created = client.post('/api/v1/guest/jobs', json={
            'quote_id': priced['id'], 'operation_id': str(uuid4())})
        assert created.status_code == 201
        blocked = client.post('/api/v1/guest/claim', json={
            'email': 'http-guest@example.invalid', 'display_name': 'HTTP Guest',
            'password': 'synthetic-password-only'})
        assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'guest_job_active'

        claim = runner.claim()
        assert claim is not None
        from izo.jobs.worker import render_test_image
        runner.execute(claim, render_test_image)
        result = client.get('/api/v1/guest/jobs/' + created.json()['id']).json()
        assert result['status'] == 'succeeded' and result['asset_id']
        assert client.get('/api/v1/guest/assets/' + result['asset_id']).status_code == 200
        image = client.get('/api/v1/guest/assets/' + result['asset_id'] + '/content')
        assert image.status_code == 200 and image.headers['content-type'] == 'image/png'

        registered = client.post('/api/v1/guest/claim', json={
            'email': 'http-guest@example.invalid', 'display_name': 'HTTP Guest',
            'password': 'synthetic-password-only'})
        assert registered.status_code == 201
        assert registered.json()['account']['id'] == guest['account_id']
        assert client.get('/api/v1/guest/me').status_code == 401
        normal = auth.me(client.cookies.get(auth.policy.cookie_name))
        assert str(normal.account.id) == guest['account_id']
