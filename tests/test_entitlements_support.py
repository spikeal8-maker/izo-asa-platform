"""Shared Entitlements fixtures/helpers; no test cases live here."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import tables as account_tables
from izo.entitlements import tables as t
from izo.entitlements.schemas import PlanPolicy, ImageSize, PublishPlan, SetDefault, AssignPlan, EntitlementError
from izo.entitlements.policy import ImageDemand, RuntimeState, UsageSnapshot
from izo.entitlements.service import EntitlementService
from credit_support import grant

# Reuse the canonical Credits fixture without copying its setup into Entitlements tests.
pytest_plugins = ("credit_support",)


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
    _, svc, owner, _, staff, _, credits = e
    rev = publish(conn, svc, staff)
    default(conn, svc, staff, rev)
    grant(conn, credits, owner, staff)
    return rev
