"""Provider cancellation, lease recovery and account-state safety."""
from uuid import uuid4

import sqlalchemy as sa

from izo.accounts import tables as a
from izo.jobs import tables as j
from izo.jobs.provider_execution import FalJobExecutor, recover_fal
from izo.providers.fal import FalRequestMissing, FalStatus
from provider_job_support import FakeAdapter, balances, create_provider, env


def _persist_known(service, job, clock, request_id, *, state="accepted"):
    base = f"https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/{request_id}"
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(
            id=uuid4(), job_id=job.id, provider="fal",
            connection_id="fal-klein-4b-v1", credential_ref="env:IZO_FAL_KEY:v1",
            provider_request_id=request_id, status_url=base + "/status", response_url=base,
            cancel_url=base + "/cancel", state=state, estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None,
            created_at=clock[0], updated_at=clock[0]))


def test_cancelled_external_job_with_provider_intent_is_not_refunded_by_http_request(env):
    service, runner, users, clock, _, _, _, job = create_provider(env)
    claim = runner.claim(); runner.start(claim)
    _persist_known(service, job, clock, "request_active", state="running")
    response = service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    assert response.status == "running" and response.cancel_requested
    assert balances(env).wallet.reserved == 1 and balances(env).wallet.available == 99


def test_recovered_queued_provider_request_cannot_be_refunded_by_http_cancel(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim(); runner.start(claim)
    _persist_known(service, job, clock, "request_requeued")
    clock[0] += 31
    assert recover_fal(runner) == 1
    cancelled = service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    assert cancelled.status == "queued" and cancelled.cancel_requested
    assert balances(env).wallet.reserved == 1 and balances(env).wallet.available == 99
    adapter = FakeAdapter(draft, statuses=[FalStatus("COMPLETED")])
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim(resume_external=True))
    done = service.get(users[0].bearer, job.id)
    assert done.status == "succeeded" and done.cancel_requested and done.charged_credits == 1
    assert adapter.submit_count == 0 and balances(env).wallet.available == 99


def test_queue_cancel_confirmation_refunds_only_after_provider_confirms_removal(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    def request_cancel(_):
        service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    adapter = FakeAdapter(draft, statuses=[FalStatus("IN_QUEUE"),
        FalRequestMissing("provider_request_missing")], on_submit=request_cancel)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    assert service.get(users[0].bearer, job.id).status == "cancelled"
    assert adapter.cancel_count == 1 and balances(env).wallet.available == 100


def test_queue_cancel_202_can_race_into_progress_and_must_not_refund(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    def request_cancel(_):
        service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    adapter = FakeAdapter(draft, statuses=[FalStatus("IN_QUEUE"), FalStatus("IN_PROGRESS"),
                                          FalStatus("COMPLETED")], on_submit=request_cancel)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    done = service.get(users[0].bearer, job.id)
    assert done.status == "succeeded" and done.cancel_requested and done.charged_credits == 1
    assert adapter.cancel_count == 1 and balances(env).wallet.available == 99


def test_in_progress_cancel_can_still_complete_and_settle_without_false_refund(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    adapter = FakeAdapter(draft, statuses=[FalStatus("IN_PROGRESS"),
        FalStatus("IN_PROGRESS"), FalStatus("COMPLETED")])
    def late_cancel(count):
        if count == 1:
            service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    adapter.on_status = late_cancel
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    done = service.get(users[0].bearer, job.id)
    assert done.status == "succeeded" and done.cancel_requested and done.charged_credits == 1
    assert adapter.cancel_count == 1


def test_expired_new_provider_job_is_never_submitted(env):
    service, runner, users, clock, _, _, _, job = create_provider(env)
    clock[0] += 901
    assert runner.claim(resume_external=True) is None
    result = service.get(users[0].bearer, job.id)
    assert result.status == "failed" and result.error_code == "admission_expired"
    assert balances(env).wallet.available == 100
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(j.provider_calls)).scalar_one() == 0


def test_late_submit_response_persists_request_id_after_lease_recovery(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    def expire_during_submit(_):
        clock[0] += 31
        assert recover_fal(runner) == 1
    first = FakeAdapter(draft, on_submit=expire_during_submit)
    FalJobExecutor(runner, first, sleeper=lambda _: None).execute(runner.claim())
    recovered = service.get(users[0].bearer, job.id)
    assert recovered.status == "queued" and recovered.error_code is None
    with service.auth.engine.connect() as conn:
        call = conn.execute(sa.select(j.provider_calls).where(
            j.provider_calls.c.job_id == job.id)).mappings().one()
        assert call["provider_request_id"] == "request_12345678"
    assert first.submit_count == 1 and balances(env).wallet.reserved == 1
    resumed = FakeAdapter(draft)
    FalJobExecutor(runner, resumed, sleeper=lambda _: None).execute(runner.claim(resume_external=True))
    assert resumed.submit_count == 0
    assert service.get(users[0].bearer, job.id).status == "succeeded"
    assert balances(env).wallet.available == 99


def test_known_provider_request_resumes_even_after_account_restriction(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim(); runner.start(claim)
    _persist_known(service, job, clock, "request_restricted")
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(a.accounts).where(
            a.accounts.c.id == users[0].view.account.id).values(state="generation_suspended"))
    clock[0] += 31
    assert recover_fal(runner) == 1
    resumed = runner.claim(resume_external=True)
    assert resumed is not None
    FalJobExecutor(runner, FakeAdapter(draft), sleeper=lambda _: None).execute(resumed)
    result = service.get(users[0].bearer, job.id)
    assert result.status == "succeeded" and result.charged_credits == 1
    assert balances(env).wallet.available == 99


def test_account_restriction_after_provider_acceptance_does_not_create_false_refund(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    adapter = FakeAdapter(draft, statuses=[FalStatus("COMPLETED")])
    def restrict_after_submit(count):
        if count == 1:
            with service.auth.engine.begin() as conn:
                conn.execute(sa.update(a.accounts).where(
                    a.accounts.c.id == users[0].view.account.id)
                    .values(state="generation_suspended"))
    adapter.on_status = restrict_after_submit
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == "succeeded" and result.charged_credits == 1
    assert balances(env).wallet.available == 99 and balances(env).wallet.reserved == 0
