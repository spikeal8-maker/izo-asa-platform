"""ENTITLEMENT-001 real PG/HTTP/races/restart. Explicit isolated CI only.

Private fixture stdout must go to RUNNER_TEMP with umask077, never an artifact.
This checks policy persistence, not unimplemented Jobs/Media allocation.
"""
import http.client
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from auth_acceptance import Client, check
from izo.config import Settings
from izo.accounts import repository as ar, tables as accounts
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.credits.service import CreditService
from izo.credits.schemas import Grant
from izo.entitlements.service import EntitlementService
from izo.entitlements.schemas import (
    PlanPolicy, ImageSize, PublishPlan, SetDefault, AssignPlan, EntitlementError)
from izo.entitlements.policy import ImageDemand, RuntimeState, UsageSnapshot
from izo.entitlements import tables as t


def read(client, query=''):
    conn=http.client.HTTPConnection('api',8000,timeout=15)
    try:
        h={'cookie':client.name+'='+client.raw} if client.raw else {}
        conn.request('GET','/api/v1/entitlements'+query,headers=h)
        response=conn.getresponse()
        return response.status,json.loads(response.read(65536))
    finally:
        conn.close()


def race(engine, functions):
    gate=Barrier(len(functions))
    def run(fn):
        gate.wait(timeout=10)
        try:
            with engine.begin() as conn:
                return fn(conn)
        except EntitlementError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(run,functions))


def policy(active=2):
    return PlanPolicy(capability_ids=('image.test',),executors=('api','local'),
        active_jobs=active,submissions=10,window_seconds=60,storage_bytes=1000,
        upload_bytes=100,input_count=2,image_sizes=(ImageSize(width=512,height=512),),
        max_action_credits=100)


def immutable(engine):
    commands=[
        'UPDATE entitlement_revisions SET revision=revision',
        'DELETE FROM entitlement_revisions',
        'UPDATE entitlement_changes SET reason=reason',
        'DELETE FROM entitlement_changes',
        'TRUNCATE entitlement_changes',
        'TRUNCATE entitlement_revisions, entitlement_default, entitlement_assignments, entitlement_changes',
    ]
    for sql in commands:
        try:
            with engine.begin() as conn:
                conn.execute(sa.text(sql))
        except DBAPIError as exc:
            check(getattr(exc.orig,'sqlstate',None)=='55000','entitlement_immutable_sqlstate')
        else:
            raise AssertionError('entitlement_history_mutated')


def before(auth,svc):
    clients=[]; ids=[]
    for role in ['owner','other','operator-a','operator-b']:
        client=Client(auth.policy.cookie_name)
        status,body=client.call('POST','/register',dict(email='ent-ci-'+uuid4().hex+'@example.invalid',
            password=secrets.token_urlsafe(32),display_name='Entitlement CI '+role,
            invite_code=auth.issue_invite()))
        check(status==201,'entitlement_signup')
        clients.append(client); ids.append(UUID(body['account']['id']))
    owner,other,staff,staff_b=ids
    with auth.engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(accounts.identities.c.account_id.in_(ids))
                     .values(verified_at=auth.now()))
        for actor in [staff,staff_b]:
            conn.execute(sa.insert(accounts.permissions).values(account_id=actor,permission='plans.write'))
        conn.execute(sa.insert(accounts.permissions).values(account_id=staff,permission='credits.grant'))
        CreditService().grant(conn,owner,staff,Grant(operation_id=uuid4(),case_id=uuid4(),
            amount=100,reason='test_grant'),grant_limit=100)
        basic=PublishPlan(operation_id=uuid4(),reason='CI basic',revision_id=uuid4(),
            plan_code='basic',revision=1,policy=policy())
        extra=PublishPlan(operation_id=uuid4(),reason='CI custom',revision_id=uuid4(),
            plan_code='custom',revision=1,policy=policy(3))
        next_base=PublishPlan(operation_id=uuid4(),reason='CI next basic',revision_id=uuid4(),
            plan_code='basic',revision=2,policy=policy(1))
        for command in [basic,extra,next_base]: svc.publish(conn,staff,command)
        svc.set_default(conn,staff,SetDefault(operation_id=uuid4(),reason='CI default',
            revision_id=basic.revision_id,expected_version=0))
    end=auth.now()+3600
    commands=[AssignPlan(operation_id=uuid4(),reason='CI concurrent assignment',
        revision_id=extra.revision_id,expected_version=0,starts_at=auth.now(),expires_at=end) for _ in range(2)]
    actors=[staff,staff_b]
    results=race(auth.engine,[lambda conn,i=i:svc.assign(conn,actors[i],owner,commands[i]) for i in range(2)])
    check(results.count('revision_conflict')==1,'one_assignment_version_wins')
    winner=next(i for i,result in enumerate(results) if not isinstance(result,str))
    retries=race(auth.engine,[lambda conn:svc.assign(conn,actors[winner],owner,commands[winner])]*2)
    check(retries[0]==retries[1]==results[winner],'assignment_retry_single_effect')
    defaults=[SetDefault(operation_id=uuid4(),reason='CI concurrent default',
        revision_id=next_base.revision_id,expected_version=1) for _ in range(2)]
    results=race(auth.engine,[lambda conn,i=i:svc.set_default(conn,actors[i],defaults[i]) for i in range(2)])
    check(results.count('revision_conflict')==1,'default_revision_conflict')
    immutable(auth.engine)
    status,view=read(clients[0]); status_b,view_b=read(clients[1])
    check(status==status_b==200 and view['source']=='assignment' and view_b['source']=='basic','own_plan_http')
    check(view['policy']['active_jobs']==3 and view_b['policy']['active_jobs']==1,'no_cross_account_plan')
    check(read(Client(auth.policy.cookie_name))[0]==401,'entitlement_guest_denied')
    check(read(clients[0],'?account_id='+str(other))[0]==422,'entitlement_owner_injection_denied')
    fixed=auth.now(); preview=EntitlementService(clock=lambda:fixed)
    demand=ImageDemand(capability_id='image.test',executor='api',size=ImageSize(width=512,height=512),
        input_count=0,largest_input_bytes=0,output_bytes_bound=100,reserve_credits=10)
    runtime=RuntimeState(feature_enabled=True,capability_supported=True,provider_available=True)
    usage=UsageSnapshot(account_id=owner,as_of=fixed,window_seconds=60,active_jobs=0,
        submissions=0,committed_bytes=0,reserved_bytes=0)
    with auth.engine.begin() as conn:
        check(preview.assess_image(conn,owner,demand,runtime,usage).allowed,'actual_pg_policy_preview')
        check(preview.assess_image(conn,owner,demand,runtime).code=='usage_unavailable','unknown_usage_denied')
        check(CreditService().overview(conn,owner).balance.available==100,'plan_preview_not_charge')
    print('ENTITLEMENT_BEFORE_OK: PG version races/replay, immutable revisions, owner HTTP and nonspending preview',file=sys.stderr)
    print(json.dumps(dict(schema=1,owner=str(owner),actor=str(actors[winner]),cookie_name=clients[0].name,
        cookie=clients[0].raw,expected_hash=view['policy_hash'],default_id=str(next_base.revision_id),
        assignment=commands[winner].model_dump(mode='json'),expires_at=end)))


def after(auth,svc):
    item=json.loads(sys.stdin.read(16384));check(item['schema']==1,'entitlement_fixture_schema')
    owner,actor=UUID(item['owner']),UUID(item['actor'])
    client=Client(item['cookie_name'],item['cookie'])
    status,account=client.call('GET','/me')
    check(status==200 and account['account']['id']==str(owner) and
        account['account']['email'].startswith('ent-ci-') and
        account['account']['email'].endswith('@example.invalid'),'entitlement_fixture_identity')
    status,view=read(client)
    check(status==200 and view['policy_hash']==item['expected_hash'] and view['assignment_version']==1,
          'entitlements_survive_restart')
    command=AssignPlan.model_validate_json(json.dumps(item['assignment']))
    with auth.engine.begin() as conn:
        check(svc.assign(conn,actor,owner,command).version==1,'assignment_replay_after_restart')
        expired=EntitlementService(clock=lambda:item['expires_at']).resolve(conn,owner)
        check(expired.assignment_state=='expired' and str(expired.revision_id)==item['default_id'],
              'expiry_uses_current_basic_revision')
        balance=CreditService().overview(conn,owner).balance
        check(balance.available==100 and balance.sequence==1,'expiry_not_ledger_mutation')
    print('ENTITLEMENT_AFTER_OK: assignment/default/history persisted; replay unchanged; logical-clock expiry preserves credits')


def main():
    config=Settings()
    if (config.environment!='test' or config.pg_host!='postgres' or config.pg_database!='izo'
            or os.environ.get('IZO_ENTITLEMENT_ACCEPTANCE')!='isolated'):
        raise SystemExit('Refusing entitlement acceptance outside isolated CI')
    engine=ar.create_auth_engine(config)
    try:
        auth=AuthService(engine,AuthSettings());svc=EntitlementService()
        phase=sys.argv[1] if len(sys.argv)==2 else ''
        if phase=='before': before(auth,svc)
        elif phase=='after': after(auth,svc)
        else: raise ValueError('Expected before or after')
    except Exception as exc:
        print('ENTITLEMENT_ACCEPTANCE_FAILED: '+type(exc).__name__,file=sys.stderr)
        if isinstance(exc,AssertionError): print(str(exc),file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
