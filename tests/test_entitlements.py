"""Real policy persistence with existing Credits; SQLite does not prove PG locks."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.accounts import tables as account_tables, entitlement_access
from izo.credits import tables as credit_tables
from izo.credits.schemas import Reserve, Release
from izo.entitlements import tables as t, repository as repo
from izo.entitlements.schemas import (
    PlanPolicy, ImageSize, PublishPlan, SetDefault, AssignPlan, EntitlementError)
from izo.entitlements.policy import ImageDemand, RuntimeState, UsageSnapshot
from izo.entitlements.service import EntitlementService
from test_credits import credit_env, grant


@pytest.fixture
def env(credit_env):
    engine, credits, owner, other, staff = credit_env
    clock = [2000]
    service = EntitlementService(clock=lambda: clock[0])
    with engine.begin() as conn:
        conn.execute(sa.insert(t.defaults).values(id=1, version=0))
        conn.execute(sa.insert(account_tables.permissions).values(account_id=staff, permission='plans.write'))
    return engine, service, owner, other, staff, clock, credits


def policy(**updates):
    values = dict(capability_ids=('image.test',), executors=('api', 'local'), active_jobs=2,
        submissions=10, window_seconds=60, storage_bytes=1000, upload_bytes=100,
        input_count=2, image_sizes=(ImageSize(width=512, height=512),), max_action_credits=100)
    values.update(updates)
    return PlanPolicy(**values)


def publish(conn, service, staff, code='basic', version=1, **values):
    cmd = PublishPlan(operation_id=uuid4(), reason='synthetic fixture', revision_id=uuid4(),
        plan_code=code, revision=version, policy=policy(**values))
    service.publish(conn, staff, cmd)
    return cmd


def default(conn, service, staff, revision, version=0):
    cmd = SetDefault(operation_id=uuid4(), reason='fixture default', revision_id=revision.revision_id,
                     expected_version=version)
    service.set_default(conn, staff, cmd)
    return cmd


def assign(conn, service, staff, owner, revision, **kw):
    args = dict(operation_id=uuid4(), reason='fixture assignment',
        revision_id=revision.revision_id if revision else None, expected_version=0,
        starts_at=2000 if revision else None, expires_at=2010 if revision else None)
    args.update(kw)
    cmd = AssignPlan(**args)
    service.assign(conn, staff, owner, cmd)
    return cmd


def demand(**kw):
    return ImageDemand(**(dict(capability_id='image.test', executor='api',
        size=ImageSize(width=512, height=512), input_count=0, largest_input_bytes=0,
        output_bytes_bound=100, reserve_credits=10) | kw))


def usage(owner, **kw):
    return UsageSnapshot(**(dict(account_id=owner, as_of=2000, window_seconds=60,
        active_jobs=0, submissions=0, committed_bytes=0, reserved_bytes=0) | kw))


def runtime(**kw):
    return RuntimeState(**(dict(feature_enabled=True, capability_supported=True,
                              provider_available=True) | kw))


def expect(code, action):
    with pytest.raises(EntitlementError) as exc:
        action()
    assert exc.value.code == code


def setup(conn, e):
    _, svc, owner, other, staff, _, credits = e
    rev = publish(conn, svc, staff)
    default(conn, svc, staff, rev)
    grant(conn, credits, owner, staff)
    return rev


def test_unconfigured_is_explicit_no_bonus_or_wallet(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        view = svc.resolve(conn, owner)
        assert not view.configured and view.policy is None and view.source == 'none'
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner)).code == 'plan_unconfigured'
        assert conn.execute(sa.select(sa.func.count()).select_from(credit_tables.wallets)).scalar_one() == 0


def test_allowed_is_preview_not_admission_or_charge(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        result = svc.assess_image(conn, owner, demand(), runtime(), usage(owner))
        assert result.allowed and not result.admission_reserved
        assert conn.execute(sa.select(sa.func.count()).select_from(credit_tables.ledger)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(credit_tables.reservations)).scalar_one() == 0


def test_schedule_expiry_falls_back_without_balance_changes(env):
    engine, svc, owner, _, staff, clock, credits = env
    with engine.begin() as conn:
        base = setup(conn, env)
        extra = publish(conn, svc, staff, 'extended', active_jobs=4)
        assign(conn, svc, staff, owner, extra, starts_at=2002, expires_at=2005)
        assert svc.resolve(conn, owner).assignment_state == 'scheduled'
        assert svc.resolve(conn, owner).revision_id == base.revision_id
        clock[0] = 2002
        snapshot = svc.resolve(conn, owner)
        assert snapshot.revision_id == extra.revision_id
        clock[0] = 2005
        after = svc.resolve(conn, owner)
        assert after.assignment_state == 'expired' and after.revision_id == base.revision_id
        assert snapshot.policy.active_jobs == 4
        assert credits.overview(conn, owner).balance.available == 100
        assert credits.overview(conn, owner).balance.sequence == 1


def test_future_default_does_not_rewrite_assignment_or_snapshot(env):
    engine, svc, owner, _, staff, clock, _ = env
    with engine.begin() as conn:
        setup(conn, env)
        extra = publish(conn, svc, staff, 'custom')
        assign(conn, svc, staff, owner, extra)
        old = svc.resolve(conn, owner)
        new = publish(conn, svc, staff, version=2, active_jobs=1)
        default(conn, svc, staff, new, version=1)
        assert svc.resolve(conn, owner).revision_id == extra.revision_id
        clock[0] = 2010
        assert svc.resolve(conn, owner).revision_id == new.revision_id
        assert old.policy.active_jobs == 2


@pytest.mark.parametrize('action', ['publish', 'default', 'assign'])
def test_permission_checked_no_self_upgrade(env, action):
    engine, svc, owner, other, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff)
        fn = {'publish': lambda: publish(conn, svc, owner, version=2),
              'default': lambda: default(conn, svc, owner, rev),
              'assign': lambda: assign(conn, svc, owner, other, rev)}[action]
        expect('plan_write_forbidden', fn)


@pytest.mark.parametrize('state', ['generation_suspended', 'security_locked', 'deletion_pending', 'deleted'])
def test_staff_state_and_expired_permission_apply(env, state):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        conn.execute(sa.update(account_tables.accounts).where(account_tables.accounts.c.id == staff).values(state=state))
        expect('plan_write_forbidden', lambda: publish(conn, svc, staff))


def test_expired_staff_permission_denies_even_idempotent_retry(env):
    engine, svc, owner, _, staff, clock, _ = env
    with engine.begin() as conn:
        cmd = publish(conn, svc, staff)
        conn.execute(sa.update(account_tables.permissions).where(
            account_tables.permissions.c.account_id == staff,
            account_tables.permissions.c.permission == 'plans.write').values(expires_at=2000))
        expect('plan_write_forbidden', lambda: svc.publish(conn, staff, cmd))


@pytest.mark.parametrize('kind', ['publish','default','assign'])
def test_exact_replay_and_mismatched_operation(env, kind):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff)
        if kind == 'publish':
            cmd, call = rev, lambda x: svc.publish(conn, staff, x)
        elif kind == 'default':
            cmd, call = default(conn, svc, staff, rev), lambda x: svc.set_default(conn, staff, x)
        else:
            cmd, call = assign(conn, svc, staff, owner, rev), lambda x: svc.assign(conn, staff, owner, x)
        count = conn.execute(sa.select(sa.func.count()).select_from(t.changes)).scalar_one()
        assert call(cmd) == call(cmd)
        assert conn.execute(sa.select(sa.func.count()).select_from(t.changes)).scalar_one() == count
        changed = cmd.model_copy(update={'reason': 'a different command'})
        expect('idempotency_conflict', lambda: call(changed))


@pytest.mark.parametrize('kind', ['publish','default','assign'])
def test_audit_failure_rolls_back_mutation_and_history(env, monkeypatch, kind):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff)
        before = [conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
                  for table in (t.revisions, t.changes, t.assignments, account_tables.audit)]
        def fail(*a):
            raise RuntimeError('synthetic audit failure')
        monkeypatch.setattr(entitlement_access, 'record_event', fail)
        with pytest.raises(RuntimeError, match='synthetic'):
            if kind == 'publish': publish(conn, svc, staff, version=2)
            elif kind == 'default': default(conn, svc, staff, rev)
            else: assign(conn, svc, staff, owner, rev)
        after = [conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
                 for table in (t.revisions, t.changes, t.assignments, account_tables.audit)]
        assert before == after
        assert conn.execute(sa.select(t.defaults.c.version)).scalar_one() == 0


def test_clear_assignment_uses_version_and_returns_basic(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        base = setup(conn, env)
        extra = publish(conn, svc, staff, 'custom')
        assign(conn, svc, staff, owner, extra)
        expect('revision_conflict', lambda: assign(conn, svc, staff, owner, None))
        assign(conn, svc, staff, owner, None, expected_version=1)
        assert svc.resolve(conn, owner).revision_id == base.revision_id
        assert svc.resolve(conn, owner).assignment_version == 2


def test_non_basic_default_and_duplicate_revision_rejected(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff, 'extended')
        expect('basic_default_required', lambda: default(conn, svc, staff, rev))
        expect('entitlement_conflict', lambda: publish(conn, svc, staff, 'extended'))
        assert conn.execute(sa.select(t.defaults.c.version)).scalar_one() == 0


def test_corrupted_policy_fails_closed(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        rev = setup(conn, env)
        # SQLite lacks the PostgreSQL immutable trigger; simulate privileged corruption.
        conn.execute(sa.update(t.revisions).where(t.revisions.c.id==rev.revision_id).values(policy_json='{}'))
        expect('invalid_policy', lambda: svc.resolve(conn, owner))


@pytest.mark.parametrize('data,code', [
    ({'capability_id':'image.other'},'plan_restricted'),
    ({'size':ImageSize(width=1024,height=1024)},'image_size_restricted'),
    ({'input_count':3,'largest_input_bytes':50},'input_limit'),
    ({'input_count':1,'largest_input_bytes':101},'input_limit'),
    ({'input_count':0,'largest_input_bytes':1},'invalid_input_usage'),
    ({'reserve_credits':101},'action_budget_exceeded'),
])
def test_demand_limits(env, data, code):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn,owner,demand(**data),runtime(),usage(owner)).code == code


@pytest.mark.parametrize('data,code', [
    ({'active_jobs':2},'concurrency_limit'), ({'submissions':10},'rate_limited'),
    ({'committed_bytes':900,'reserved_bytes':1},'storage_quota_exceeded'),
    ({'as_of':1999},'usage_unavailable'), ({'as_of':2001},'usage_unavailable'),
    ({'window_seconds':61},'usage_unavailable'), ({'account_id':uuid4()},'usage_unavailable'),
])
def test_usage_limits_and_owner(env, data, code):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn,owner,demand(),runtime(),usage(owner,**data)).code == code


def test_missing_usage_is_not_zero(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn,owner,demand(),runtime()).code == 'usage_unavailable'


@pytest.mark.parametrize('data,code', [
    ({'feature_enabled':False},'feature_unavailable'),
    ({'capability_supported':False},'capability_unsupported'),
    ({'provider_available':False},'provider_unavailable'),
])
def test_provider_or_feature_not_replaced_with_silent_fallback(env, data, code):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn,owner,demand(),runtime(**data),usage(owner)).code == code
        assert svc.assess_image(conn,owner,demand(executor='local'),runtime(),usage(owner)).allowed


def test_balance_reserve_is_read_from_real_credit_module(env):
    engine, svc, owner, _, staff, _, credits = env
    with engine.begin() as conn:
        setup(conn, env)
        hold = Reserve(operation_id=uuid4(), reservation_id=uuid4(), request_id=uuid4(), amount=95)
        credits.reserve(conn,owner,hold)
        assert svc.assess_image(conn,owner,demand(),runtime(),usage(owner)).code == 'insufficient_credits'
        credits.release(conn,owner,Release(operation_id=uuid4(),reservation_id=hold.reservation_id))
        assert svc.assess_image(conn,owner,demand(),runtime(),usage(owner)).allowed


def test_unverified_and_suspended_still_can_read_own_policy(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        conn.execute(sa.update(account_tables.identities).where(account_tables.identities.c.account_id==owner).values(verified_at=None))
        assert svc.resolve(conn,owner).configured
        assert svc.assess_image(conn,owner,demand(),runtime(),usage(owner)).code == 'verification_required'
        conn.execute(sa.update(account_tables.accounts).where(account_tables.accounts.c.id==owner).values(state='generation_suspended'))
        assert svc.resolve(conn,owner).configured
        assert svc.assess_image(conn,owner,demand(),runtime(),usage(owner)).code == 'account_restricted'


@pytest.mark.parametrize('data', [
    {'active_jobs':True}, {'submissions':-1}, {'storage_bytes':None},
    {'upload_bytes':1001,'storage_bytes':1000}, {'max_action_credits':1.5},
    {'active_jobs':'2'}, {'role':'admin'}, {'executors':('other',)},
    {'capability_ids':('image.test','image.test')}, {'can_publish':'yes'},
    {'image_sizes':(ImageSize(width=1,height=1),)*2}, {'window_seconds':0},
])
def test_malformed_policy_rejected(data):
    with pytest.raises(ValidationError): policy(**data)


def test_frozen_policy_revalidates_forged_copy(env):
    engine, svc, owner, _, staff, *_ = env
    bad = policy().model_copy(update={'active_jobs':-1})
    with pytest.raises(ValidationError):
        PublishPlan(operation_id=uuid4(),reason='test', revision_id=uuid4(),plan_code='basic',revision=1,policy=bad)


def test_zero_values_deny_not_unlimited(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev=publish(conn,svc,staff,active_jobs=0)
        default(conn,svc,staff,rev)
        assert svc.assess_image(conn,owner,demand(reserve_credits=0),runtime(),usage(owner)).code=='concurrency_limit'


def test_plan_does_not_grant_staff_permissions(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev=publish(conn,svc,staff,'custom')
        assign(conn,svc,staff,owner,rev)
        assert not entitlement_access.may_write(conn,owner,2000)
        expect('plan_write_forbidden',lambda: publish(conn,svc,owner,version=2))
