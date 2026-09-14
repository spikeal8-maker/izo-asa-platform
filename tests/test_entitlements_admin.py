"""Entitlements administrative mutation, replay and audit tests."""
import pytest
import sqlalchemy as sa

from izo.accounts import tables as account_tables, entitlement_access
from izo.entitlements import tables as t
from test_entitlements_support import env, publish, default, assign, expect


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
    engine, svc, _, _, staff, *_ = env
    with engine.begin() as conn:
        conn.execute(sa.update(account_tables.accounts).where(account_tables.accounts.c.id == staff).values(state=state))
        expect('plan_write_forbidden', lambda: publish(conn, svc, staff))


def test_expired_staff_permission_denies_even_idempotent_retry(env):
    engine, svc, _, _, staff, *_ = env
    with engine.begin() as conn:
        cmd = publish(conn, svc, staff)
        conn.execute(sa.update(account_tables.permissions).where(
            account_tables.permissions.c.account_id == staff,
            account_tables.permissions.c.permission == 'plans.write').values(expires_at=2000))
        expect('plan_write_forbidden', lambda: svc.publish(conn, staff, cmd))


@pytest.mark.parametrize('kind', ['publish', 'default', 'assign'])
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


@pytest.mark.parametrize('kind', ['publish', 'default', 'assign'])
def test_audit_failure_rolls_back_mutation_and_history(env, monkeypatch, kind):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff)
        before = [conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
                  for table in (t.revisions, t.changes, t.assignments, account_tables.audit)]
        def fail(*_args):
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
