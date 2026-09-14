"""Core Entitlements assessment test plus compatibility helper exports."""
import sqlalchemy as sa

from izo.credits import tables as credit_tables
from test_entitlements_support import assign, default, demand, env, expect, policy, publish, runtime, setup, usage


def test_allowed_is_preview_not_admission_or_charge(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        result = svc.assess_image(conn, owner, demand(), runtime(), usage(owner))
        assert result.allowed and not result.admission_reserved
        assert conn.execute(sa.select(sa.func.count()).select_from(credit_tables.ledger)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(credit_tables.reservations)).scalar_one() == 0


__all__ = ["assign", "default", "demand", "env", "expect", "policy", "publish", "runtime", "setup", "usage"]
