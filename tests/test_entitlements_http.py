"""Own plan through real AuthService/session rows; fake network is not used."""
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from izo.accounts import repository as ar, tables as at
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.accounts.security import AuthError
from izo.entitlements.routes import attach_entitlements
from test_credits import credit_env
from test_entitlements import env, setup, publish, assign


@pytest.fixture
def http_env(env):
    engine, svc, owner, other, staff, clock, credits = env
    auth=AuthService(engine, AuthSettings(rate_secret='synthetic-not-a-live-secret-'+'x'*32), clock=lambda:clock[0])
    with engine.begin() as conn:
        setup(conn,env)
        extra=publish(conn,svc,staff,'custom',active_jobs=5)
        assign(conn,svc,staff,owner,extra)
        first=auth._new_session(conn,ar.account_by_id(conn,owner),'synthetic',2000)
        second=auth._new_session(conn,ar.account_by_id(conn,other),'synthetic',2000)
    app=FastAPI()
    @app.exception_handler(AuthError)
    async def error(request,exc):
        return JSONResponse({'error':{'code':exc.code}},status_code=exc.status)
    attach_entitlements(app,lambda request:auth)
    with TestClient(app) as client:
        yield client,auth,first,second,env


def headers(auth,session):
    return {'cookie':auth.policy.cookie_name+'='+session.bearer}


def test_each_session_reads_its_own_plan(http_env):
    client,auth,a,b,env=http_env
    first=client.get('/api/v1/entitlements',headers=headers(auth,a))
    second=client.get('/api/v1/entitlements',headers=headers(auth,b))
    assert first.status_code==second.status_code==200
    assert first.json()['account_id']==str(a.view.account.id)
    assert second.json()['account_id']==str(b.view.account.id)
    assert first.json()['policy']['active_jobs']==5
    assert second.json()['policy']['active_jobs']==2
    for forbidden in ['csrf_token','bearer','reason','actor_id','fingerprint']:
        assert forbidden not in first.json()


@pytest.mark.parametrize('query',['?account_id=other','?role=admin','?plan=custom','?x=1&x=2'])
def test_client_cannot_choose_identity_or_plan(http_env,query):
    client,auth,a,*_=http_env
    assert client.get('/api/v1/entitlements'+query,headers=headers(auth,a)).status_code==422


@pytest.mark.parametrize('raw',[None,'a'*43,'invalid'])
def test_anonymous_or_forged_session_denied(http_env,raw):
    client,auth,*_=http_env
    h={'cookie':auth.policy.cookie_name+'='+raw} if raw else {}
    assert client.get('/api/v1/entitlements',headers=h).status_code==401


def test_revoked_session_not_reused(http_env):
    client,auth,a,*_=http_env
    auth.revoke(a.bearer,a.view.csrf_token)
    assert client.get('/api/v1/entitlements',headers=headers(auth,a)).status_code==401


@pytest.mark.parametrize('state,status',[('generation_suspended',200),('security_locked',401),('deletion_pending',403),('deleted',401)])
def test_current_account_state_is_rechecked(http_env,state,status):
    client,auth,a,_,env=http_env
    with auth.engine.begin() as conn:
        conn.execute(sa.update(at.accounts).where(at.accounts.c.id==a.view.account.id).values(state=state))
    assert client.get('/api/v1/entitlements',headers=headers(auth,a)).status_code==status


@pytest.mark.parametrize('path',['','/assign','/default','/publish','/assess'])
def test_no_public_plan_or_usage_mutation(http_env,path):
    client,auth,a,*_=http_env
    result=client.post('/api/v1/entitlements'+path,headers=headers(auth,a),
                       json={'role':'admin','active_jobs':0,'provider_available':True})
    assert result.status_code in {404,405}
    assert client.get('/api/v1/entitlements',headers=headers(auth,a)).json()['policy']['active_jobs']==5


def test_expiry_is_visible_in_http_without_wallet_change(http_env):
    client,auth,a,_,env=http_env
    engine,svc,owner,other,staff,clock,credits=env
    clock[0]=2010
    result=client.get('/api/v1/entitlements',headers=headers(auth,a))
    assert result.json()['assignment_state']=='expired'
    assert result.json()['policy']['active_jobs']==2
    with engine.begin() as conn:
        assert credits.overview(conn,owner).balance.available==100
