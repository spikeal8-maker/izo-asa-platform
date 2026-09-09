"""CHANGE-001/B: adjust model access through existing policy commands, not new code.

SQLite proves transactional behavior; the same change is also exercised against
real PostgreSQL by tools/jobs_access_acceptance.py in the existing Compose gate.
"""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.entitlements.schemas import PlanPolicy, PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.jobs import tables as j
from izo.jobs.schemas import CreateJob, JobError
from izo.jobs.worker import render_test_image
from izo.media import tables as m
from izo.media.service import MediaService
from test_jobs import env, create, draft, balances


def revise(service, actor, changes):
    plans = EntitlementService(clock=service.auth.clock)
    with service.auth.engine.begin() as conn:
        previous = plans.resolve(conn, actor)
        policy = PlanPolicy.model_validate(previous.policy.model_dump() | changes)
        revision = uuid4()
        plans.publish(conn, actor, PublishPlan(operation_id=uuid4(),
            revision_id=revision, plan_code="basic", revision=previous.revision + 1,
            policy=policy, reason="isolated model access change"))
        plans.set_default(conn, actor, SetDefault(operation_id=uuid4(),
            revision_id=revision, expected_version=previous.default_version,
            reason="isolated model access change"))
    return previous


@pytest.mark.parametrize("changes,code", [
    ({"capability_ids": ()}, "plan_restricted"),
    ({"executors": ()}, "plan_restricted"),
    ({"max_action_credits": 0}, "action_budget_exceeded"),
])
def test_new_policy_rejects_old_quote_without_spending_or_allocating(env, changes, code):
    service, _, users, *_ = env
    user = users[0]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    revise(service, user.view.account.id, changes)
    with pytest.raises(JobError, match=code) as failure:
        service.submit(user.bearer, user.view.csrf_token,
                       CreateJob(quote_id=quote.id, operation_id=uuid4()))
    assert failure.value.status == 409
    with pytest.raises(JobError, match=code):
        service.quote(user.bearer, user.view.csrf_token, draft())
    assert balances(env).consistent
    assert balances(env).wallet.available == 100
    assert balances(env).wallet.reserved == 0
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(j.jobs)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(m.outputs)).scalar_one() == 0


def test_model_removal_does_not_rewrite_accepted_job_or_hide_owned_result(env):
    service, runner, users, _, store = env
    user = users[0]
    job, command = create(env)
    with service.auth.engine.connect() as conn:
        snapshot = conn.execute(sa.select(j.jobs.c.plan_snapshot).where(j.jobs.c.id == job.id)).scalar_one()
    revise(service, user.view.account.id, {"capability_ids": ()})
    assert service.submit(user.bearer, user.view.csrf_token, command).id == job.id
    runner.execute(runner.claim(), render_test_image)
    result = service.get(user.bearer, job.id)
    assert result.status == "succeeded" and result.charged_credits == 1
    assert [item.id for item in MediaService(service.auth, store).list(user.bearer).assets] == [result.asset_id]
    assert balances(env).consistent and balances(env).wallet.available == 99
    assert balances(env).wallet.reserved == 0
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(j.jobs.c.plan_snapshot).where(j.jobs.c.id == job.id)).scalar_one() == snapshot


def test_restore_access_uses_current_policy_and_one_reservation(env):
    service, _, users, *_ = env
    user = users[0]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    command = CreateJob(quote_id=quote.id, operation_id=uuid4())
    revise(service, user.view.account.id, {"capability_ids": ()})
    with pytest.raises(JobError, match="plan_restricted"):
        service.submit(user.bearer, user.view.csrf_token, command)
    revise(service, user.view.account.id, {"capability_ids": ("test.image.v1",)})
    job = service.submit(user.bearer, user.view.csrf_token, command)
    assert service.submit(user.bearer, user.view.csrf_token, command).id == job.id
    assert balances(env).consistent and balances(env).wallet.reserved == 1
    assert balances(env).wallet.available == 99
