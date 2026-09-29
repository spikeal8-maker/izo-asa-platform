"""Provider submission, durable request identity and restart lifecycle."""
from uuid import uuid4

import sqlalchemy as sa

from izo.jobs import tables as j
from izo.jobs.provider_execution import FalJobExecutor, recover_fal
from izo.providers.fal import FalSubmissionUnknown
from provider_job_support import FakeAdapter, balances, create_provider, env


def test_real_capability_uses_same_job_media_and_credit_lifecycle(env):
    service, runner, users, _, store, _, draft, job = create_provider(env)
    assert job.status == "queued" and job.test_only is False and balances(env).wallet.reserved == 1
    adapter = FakeAdapter(draft)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == "succeeded" and result.charged_credits == 1 and result.asset_id
    assert adapter.submit_count == 1 and adapter.result_count == 1 and len(store.data) == 1
    assert balances(env).consistent and balances(env).wallet.available == 99
    with service.auth.engine.connect() as conn:
        call = conn.execute(sa.select(j.provider_calls).where(
            j.provider_calls.c.job_id == job.id)).mappings().one()
        assert call["state"] == "completed" and call["provider_request_id"] == "request_12345678"
        assert call["estimated_cost_microusd"] == 21 and call["reported_cost_microusd"] is None
        assert "synthetic-provider-secret" not in " ".join(str(value) for value in call.values())


def test_unknown_submit_keeps_reservations_and_is_never_automatically_retried(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    adapter = FakeAdapter(draft, submit_error=FalSubmissionUnknown("provider_submission_unknown"))
    executor = FalJobExecutor(runner, adapter, sleeper=lambda _: None)
    executor.execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == "reconciling" and result.error_code == "provider_submission_unknown"
    assert balances(env).wallet.reserved == 1 and adapter.submit_count == 1
    assert recover_fal(runner) == 0 and runner.claim() is None
    with service.auth.engine.connect() as conn:
        call = conn.execute(sa.select(j.provider_calls).where(
            j.provider_calls.c.job_id == job.id)).mappings().one()
        assert call["state"] == "submission_unknown" and call["provider_request_id"] is None


def test_restart_with_provider_request_id_polls_existing_request_without_resubmit(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = "https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_existing"
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider="fal",
            connection_id="fal-klein-4b-v1", credential_ref="env:IZO_FAL_KEY:v1",
            provider_request_id="request_existing", status_url=base + "/status", response_url=base,
            cancel_url=base + "/cancel", state="accepted", estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None,
            created_at=clock[0], updated_at=clock[0]))
    clock[0] += 31
    assert recover_fal(runner) == 1
    adapter = FakeAdapter(draft)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    assert adapter.submit_count == 0
    assert service.get(users[0].bearer, job.id).status == "succeeded"
    assert balances(env).wallet.available == 99


def test_credential_version_change_never_polls_old_request_with_unproven_scope(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = "https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_old_key"
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider="fal",
            connection_id="fal-klein-4b-v1", credential_ref="env:IZO_FAL_KEY:v0",
            provider_request_id="request_old_key", status_url=base + "/status", response_url=base,
            cancel_url=base + "/cancel", state="accepted", estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None,
            created_at=clock[0], updated_at=clock[0]))
    clock[0] += 31
    assert recover_fal(runner) == 1
    adapter = FakeAdapter(draft)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == "reconciling" and result.error_code == "provider_auth_required"
    assert adapter.submit_count == 0 and adapter.status_count == 0
    assert balances(env).wallet.reserved == 1
