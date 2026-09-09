"""CHANGE-001/B, called only by the disposable jobs acceptance fixture.

No live configuration defaults are changed: publish a revision and assign it
only to one synthetic recipient; restore that recipient's old assignment.
"""
import sys
from uuid import UUID, uuid4

import sqlalchemy as sa

from media_acceptance import checked
from izo.credits.service import CreditService
from izo.entitlements import tables as plans
from izo.entitlements.schemas import AssignPlan, PlanPolicy, PublishPlan
from izo.entitlements.service import EntitlementService
from izo.jobs import tables as j
from izo.jobs.catalog import JobSettings
from izo.jobs.schemas import CreateJob, QuoteInput
from izo.jobs.service import JobService
from izo.jobs.execution import JobRunner
from izo.jobs.worker import render_test_image


def check_model_access_change(auth, store, actor, target):
    policy_service = EntitlementService(clock=auth.clock)
    service = JobService(auth, JobSettings(enabled=True))
    owner_id, target_id = UUID(actor["id"]), UUID(target["id"])
    draft = QuoteInput(capability_id="test.image.v1", prompt="isolated access exercise", width=64, height=64)
    admitted_quote = service.quote(target["bearer"], target["csrf"], draft)
    admitted_command = CreateJob(quote_id=admitted_quote.id, operation_id=uuid4())
    admitted = service.submit(target["bearer"], target["csrf"], admitted_command)
    pending_quote = service.quote(target["bearer"], target["csrf"], draft)
    with auth.engine.begin() as conn:
        original = policy_service.resolve(conn, target_id)
        snapshot = conn.execute(sa.select(j.jobs.c.plan_snapshot).where(j.jobs.c.id == admitted.id)).scalar_one()
        wallet_before = CreditService(clock=auth.clock).overview(conn, target_id).balance
        number = conn.execute(sa.select(sa.func.max(plans.revisions.c.revision))
                              .where(plans.revisions.c.plan_code == "custom")).scalar_one()
    # End the target read transaction before actor-authorized policy writes.
    # assign() itself locks actor/target in the established sorted order.
    with auth.engine.begin() as conn:
        revision_id = uuid4()
        changed = PlanPolicy.model_validate(original.policy.model_dump() | {"capability_ids": ()})
        policy_service.publish(conn, owner_id, PublishPlan(operation_id=uuid4(),
            revision_id=revision_id, plan_code="custom", revision=number + 1,
            policy=changed, reason="isolated access exercise"))
        policy_service.assign(conn, owner_id, target_id, AssignPlan(operation_id=uuid4(),
            revision_id=revision_id, expected_version=original.assignment_version,
            starts_at=auth.now(), reason="isolated access exercise"))
    rejected = checked(auth, target, "/api/v1/jobs", CreateJob(quote_id=pending_quote.id,
        operation_id=uuid4()).model_dump(mode="json"), expected=409)
    assert rejected["error"]["code"] == "plan_restricted"
    rejected_quote = checked(auth, target, "/api/v1/jobs/quotes", draft.model_dump(mode="json"), expected=409)
    assert rejected_quote["error"]["code"] == "plan_restricted"
    with auth.engine.begin() as conn:
        assert CreditService(clock=auth.clock).overview(conn, target_id).balance == wallet_before
        assert conn.execute(sa.select(sa.func.count()).select_from(j.jobs)
                            .where(j.jobs.c.account_id == target_id)).scalar_one() == 1
    replay = checked(auth, target, "/api/v1/jobs", admitted_command.model_dump(mode="json"), expected=201)
    assert replay["id"] == str(admitted.id)
    runner = JobRunner(service, store)
    claim = runner.claim()
    assert claim is not None and claim.job_id == admitted.id
    runner.execute(claim, render_test_image)
    completed = checked(auth, target, "/api/v1/jobs/" + str(admitted.id))
    assert completed["status"] == "succeeded" and completed["charged_credits"] == 1
    ticket = checked(auth, target, "/api/v1/media/assets/" + completed["asset_id"] + "/download", {})
    assert checked(auth, target, ticket["url"]).startswith(b"\x89PNG")
    with auth.engine.begin() as conn:
        assert conn.execute(sa.select(j.jobs.c.plan_snapshot).where(j.jobs.c.id == admitted.id)).scalar_one() == snapshot
        audit = CreditService(clock=auth.clock).reconcile(conn, target_id)
        assert audit.consistent and audit.wallet.reserved == 0
        current = policy_service.resolve(conn, target_id)
    with auth.engine.begin() as conn:
        policy_service.assign(conn, owner_id, target_id, AssignPlan(operation_id=uuid4(),
            revision_id=original.revision_id, expected_version=current.assignment_version,
            starts_at=auth.now(), reason="restore isolated assignment"))
    print("CHANGE_ACCESS_OK: revoked model denies old/new quotes without new hold; accepted snapshot/replay/owned file preserved", file=sys.stderr)
