"""Credits read routes with real AuthService/session rows, isolated SQLite/ASGI."""
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import sqlalchemy as sa

from izo.accounts import repository as accounts_repo, tables as accounts_tables
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.accounts.security import AuthError
from izo.credits.routes import attach_credits
from test_credits import credit_env, grant


@pytest.fixture
def credit_http(credit_env):
    engine, credits, owner, other, staff = credit_env
    auth = AuthService(engine, AuthSettings(rate_secret="test-fixture-only-" + "x" * 32), clock=lambda: 2000)
    with engine.begin() as conn:
        owner_session = auth._new_session(conn, accounts_repo.account_by_id(conn, owner), "test", 2000)
        other_session = auth._new_session(conn, accounts_repo.account_by_id(conn, other), "test", 2000)
        grant(conn, credits, owner, staff)
    app = FastAPI()
    @app.exception_handler(AuthError)
    async def auth_error(request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
    attach_credits(app, lambda request: auth)
    with TestClient(app) as client:
        yield client, auth, owner_session, other_session, credit_env


def cookie(auth, session):
    return {"cookie": auth.policy.cookie_name + "=" + session.bearer}


def test_real_cookie_selects_only_its_account(credit_http):
    client, auth, first, second, env = credit_http
    response = client.get('/api/v1/credits', headers=cookie(auth, first))
    assert response.status_code == 200
    assert response.json()['balance']['available'] == 100
    assert response.json()['account_id'] == str(first.view.account.id)
    response = client.get('/api/v1/credits', headers=cookie(auth, second))
    assert response.status_code == 200
    assert response.json()['balance']['available'] == 0
    assert response.json()['entries'] == []


def test_logout_cookie_cannot_read_ledger(credit_http):
    client, auth, first, _, env = credit_http
    headers = cookie(auth, first)
    auth.revoke(first.bearer, first.view.csrf_token)
    response = client.get('/api/v1/credits', headers=headers)
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "auth_required"}}


@pytest.mark.parametrize('path', ['/api/v1/credits', '/api/v1/credits?account_id=forged'])
def test_anonymous_and_forged_bearer_denied(credit_http, path):
    client, auth, first, _, env = credit_http
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"cookie": auth.policy.cookie_name + "=" + "a" * 43}).status_code == 401


@pytest.mark.parametrize('query', ['account_id=forged', 'limit=0', 'limit=101', 'limit=1&limit=2',
    'limit=1.0', 'limit=-1', 'limit=' + '9'*100, 'before=0', 'role=admin', 'limit=NaN'])
def test_query_cannot_choose_owner_or_unbound_history(credit_http, query):
    client, auth, first, _, env = credit_http
    result = client.get('/api/v1/credits?' + query, headers=cookie(auth, first))
    assert result.status_code == 422
    assert result.json() == {"error": {"code": "invalid_pagination"}}


@pytest.mark.parametrize('path', ['', '/grant', '/reserve', '/settle', '/release'])
def test_no_public_balance_mutation(credit_http, path):
    client, auth, first, _, env = credit_http
    result = client.post('/api/v1/credits' + path, headers=cookie(auth, first),
                         json={"amount": 999999, "role": "admin"})
    assert result.status_code in {404, 405}
    assert client.get('/api/v1/credits', headers=cookie(auth, first)).json()['balance']['available'] == 100


@pytest.mark.parametrize('state,expected', [('generation_suspended',200), ('deletion_pending',403),
                                         ('security_locked',401), ('deleted',401)])
def test_session_and_current_account_state_apply(credit_http, state, expected):
    client, auth, first, _, env = credit_http
    with auth.engine.begin() as conn:
        conn.execute(sa.update(accounts_tables.accounts).where(
            accounts_tables.accounts.c.id == first.view.account.id).values(state=state))
    assert client.get('/api/v1/credits', headers=cookie(auth, first)).status_code == expected
