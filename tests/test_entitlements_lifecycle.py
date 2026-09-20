"""Entitlements lifecycle, resolution and assignment tests."""
import sqlalchemy as sa

from izo.accounts import tables as account_tables, entitlement_access
from izo.credits import tables as credit_tables
from test_entitlements_support import env, publish, default, assign, demand, usage, runtime, expect, setup


def test_unconfigured_is_explicit_no_bonus_or_wallet(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        view = svc.resolve(conn, owner)
        assert not view.configured and view.policy is None and view.source == 'none'
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner)).code == 'plan_unconfigured'
        assert conn.execute(sa.select(sa.func.count()).select_from(credit_tables.wallets)).scalar_one() == 0


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
    engine, svc, _, _, staff, *_ = env
    from izo.entitlements import tables as t
    with engine.begin() as conn:
        rev = publish(conn, svc, staff, 'extended')
        expect('basic_default_required', lambda: default(conn, svc, staff, rev))
        expect('entitlement_conflict', lambda: publish(conn, svc, staff, 'extended'))
        assert conn.execute(sa.select(t.defaults.c.version)).scalar_one() == 0


def test_corrupted_policy_fails_closed(env):
    engine, svc, owner, *_ = env
    from izo.entitlements import tables as t
    with engine.begin() as conn:
        rev = setup(conn, env)
        conn.execute(sa.update(t.revisions).where(t.revisions.c.id == rev.revision_id).values(policy_json='{}'))
        expect('invalid_policy', lambda: svc.resolve(conn, owner))


def test_unverified_active_account_keeps_basic_plan_while_suspension_still_blocks(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        conn.execute(sa.update(account_tables.identities).where(account_tables.identities.c.account_id == owner).values(verified_at=None))
        assert svc.resolve(conn, owner).configured
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner)).allowed
        conn.execute(sa.update(account_tables.accounts).where(account_tables.accounts.c.id == owner).values(state='generation_suspended'))
        assert svc.resolve(conn, owner).configured
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner)).code == 'account_restricted'


def test_zero_values_deny_not_unlimited(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff, active_jobs=0)
        default(conn, svc, staff, rev)
        assert svc.assess_image(conn, owner, demand(reserve_credits=0), runtime(), usage(owner)).code == 'concurrency_limit'


def test_plan_does_not_grant_staff_permissions(env):
    engine, svc, owner, _, staff, *_ = env
    with engine.begin() as conn:
        rev = publish(conn, svc, staff, 'custom')
        assign(conn, svc, staff, owner, rev)
        assert not entitlement_access.may_write(conn, owner, 2000)
        expect('plan_write_forbidden', lambda: publish(conn, svc, owner, version=2))
