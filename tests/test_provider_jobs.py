"""Durable external-provider jobs: no paid retry, no false cancellation refund, restart-safe polling."""
import ast
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa

from izo.accounts import tables as a
from izo.entitlements.schemas import PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.jobs import catalog, tables as j
from izo.jobs.execution import JobRunner
from izo.jobs.provider_execution import FalJobExecutor, recover_fal
from izo.jobs.schemas import QuoteInput, CreateJob
from izo.jobs.service import JobService
from izo.jobs.worker import render_test_image
from izo.providers.fal import (FalHandle, FalImage, FalRequestMissing, FalSettings,
                               FalStatus, FalSubmissionUnknown)
from test_jobs import env, balances

ROOT = Path(__file__).resolve().parents[1]


def provider_env(env):
    service, _, users, clock, store = env
    owner = users[0].view.account.id
    plans = EntitlementService(clock=service.auth.clock)
    with service.auth.engine.begin() as conn:
        previous = plans.resolve(conn, owner)
        policy = previous.policy.model_copy(update={
            'capability_ids': tuple(dict.fromkeys(previous.policy.capability_ids + (catalog.FAL_CAPABILITY,)))
        })
        revision = uuid4()
        plans.publish(conn, owner, PublishPlan(operation_id=uuid4(), revision_id=revision,
            plan_code='basic', revision=2, reason='fal isolated fixture', policy=policy))
        plans.set_default(conn, owner, SetDefault(operation_id=uuid4(), revision_id=revision,
            expected_version=previous.default_version, reason='fal isolated fixture'))
    fal = FalSettings(enabled=True, key='synthetic-provider-secret', price_microusd_per_mp=5000,
        max_cost_microusd=5000, poll_seconds=1)
    provider_service = JobService(service.auth, service.policy, fal)
    runner = JobRunner(provider_service, store, 'fal-test', pool=catalog.FAL_POOL)
    return provider_service, runner, users, clock, store, fal


def create_provider(env):
    service, runner, users, clock, store, fal = provider_env(env)
    user = users[0]
    draft = QuoteInput(capability_id=catalog.FAL_CAPABILITY, prompt='provider isolation', width=64, height=64)
    quote = service.quote(user.bearer, user.view.csrf_token, draft)
    job = service.submit(user.bearer, user.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    return service, runner, users, clock, store, fal, draft, job


class FakeAdapter:
    connection_id = 'fal-klein-4b-v1'
    credential_ref = 'env:IZO_FAL_KEY:v1'

    def __init__(self, draft, statuses=None, *, submit_error=None, on_status=None, on_submit=None):
        self.settings = SimpleNamespace(poll_seconds=0)
        self.draft = draft
        self.statuses = list(statuses or [FalStatus('COMPLETED')])
        self.submit_error = submit_error
        self.on_status = on_status
        self.on_submit = on_submit
        self.submit_count = self.cancel_count = self.status_count = self.result_count = 0
        base = 'https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_12345678'
        self.handle = FalHandle('request_12345678', base+'/status', base, base+'/cancel')

    def estimate(self, width, height):
        return 21

    def submit(self, draft):
        self.submit_count += 1
        if self.on_submit:
            self.on_submit(self.submit_count)
        if self.submit_error:
            raise self.submit_error
        return self.handle

    def status(self, handle):
        self.status_count += 1
        if self.on_status:
            self.on_status(self.status_count)
        value = self.statuses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def result(self, handle, **kwargs):
        self.result_count += 1
        return FalImage(render_test_image(self.draft), 'image/png')

    def cancel(self, handle):
        self.cancel_count += 1
        return 'requested'


def test_real_capability_uses_same_job_media_and_credit_lifecycle(env):
    service, runner, users, _, store, _, draft, job = create_provider(env)
    assert job.status == 'queued' and job.test_only is False and balances(env).wallet.reserved == 1
    adapter = FakeAdapter(draft)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'succeeded' and result.charged_credits == 1 and result.asset_id
    assert adapter.submit_count == 1 and adapter.result_count == 1 and len(store.data) == 1
    assert balances(env).consistent and balances(env).wallet.available == 99
    with service.auth.engine.connect() as conn:
        call = conn.execute(sa.select(j.provider_calls).where(j.provider_calls.c.job_id == job.id)).mappings().one()
        assert call['state'] == 'completed' and call['provider_request_id'] == 'request_12345678'
        assert call['estimated_cost_microusd'] == 21 and call['reported_cost_microusd'] is None
        assert 'synthetic-provider-secret' not in ' '.join(str(value) for value in call.values())


def test_unknown_submit_keeps_reservations_and_is_never_automatically_retried(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    adapter = FakeAdapter(draft, submit_error=FalSubmissionUnknown('provider_submission_unknown'))
    executor = FalJobExecutor(runner, adapter, sleeper=lambda _: None)
    executor.execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'reconciling' and result.error_code == 'provider_submission_unknown'
    assert balances(env).wallet.reserved == 1 and adapter.submit_count == 1
    assert recover_fal(runner) == 0 and runner.claim() is None
    with service.auth.engine.connect() as conn:
        call = conn.execute(sa.select(j.provider_calls).where(j.provider_calls.c.job_id == job.id)).mappings().one()
        assert call['state'] == 'submission_unknown' and call['provider_request_id'] is None


def test_restart_with_provider_request_id_polls_existing_request_without_resubmit(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = 'https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_existing'
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider='fal',
            connection_id='fal-klein-4b-v1', credential_ref='env:IZO_FAL_KEY:v1',
            provider_request_id='request_existing', status_url=base+'/status', response_url=base,
            cancel_url=base+'/cancel', state='accepted', estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None, created_at=clock[0], updated_at=clock[0]))
    clock[0] += 31
    assert recover_fal(runner) == 1
    adapter = FakeAdapter(draft)
    # Recovery must use the persisted handle; submit() is forbidden on this path.
    executor = FalJobExecutor(runner, adapter, sleeper=lambda _: None)
    executor.execute(runner.claim())
    assert adapter.submit_count == 0
    assert service.get(users[0].bearer, job.id).status == 'succeeded'
    assert balances(env).wallet.available == 99



def test_credential_version_change_never_polls_old_request_with_unproven_scope(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = 'https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_old_key'
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider='fal',
            connection_id='fal-klein-4b-v1', credential_ref='env:IZO_FAL_KEY:v0',
            provider_request_id='request_old_key', status_url=base+'/status', response_url=base,
            cancel_url=base+'/cancel', state='accepted', estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None, created_at=clock[0], updated_at=clock[0]))
    clock[0] += 31
    assert recover_fal(runner) == 1
    adapter = FakeAdapter(draft)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'reconciling' and result.error_code == 'provider_auth_required'
    assert adapter.submit_count == 0 and adapter.status_count == 0
    assert balances(env).wallet.reserved == 1

def test_cancelled_external_job_with_provider_intent_is_not_refunded_by_http_request(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = 'https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_active'
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider='fal',
            connection_id='fal-klein-4b-v1', credential_ref='env:IZO_FAL_KEY:v1',
            provider_request_id='request_active', status_url=base+'/status', response_url=base,
            cancel_url=base+'/cancel', state='running', estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None, created_at=clock[0], updated_at=clock[0]))
    response = service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    assert response.status == 'running' and response.cancel_requested
    assert balances(env).wallet.reserved == 1 and balances(env).wallet.available == 99


def test_recovered_queued_provider_request_cannot_be_refunded_by_http_cancel(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = 'https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_requeued'
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider='fal',
            connection_id='fal-klein-4b-v1', credential_ref='env:IZO_FAL_KEY:v1',
            provider_request_id='request_requeued', status_url=base+'/status', response_url=base,
            cancel_url=base+'/cancel', state='accepted', estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None, created_at=clock[0], updated_at=clock[0]))
    clock[0] += 31
    assert recover_fal(runner) == 1
    cancelled = service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    assert cancelled.status == 'queued' and cancelled.cancel_requested
    assert balances(env).wallet.reserved == 1 and balances(env).wallet.available == 99
    adapter = FakeAdapter(draft, statuses=[FalStatus('COMPLETED')])
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim(resume_external=True))
    done = service.get(users[0].bearer, job.id)
    assert done.status == 'succeeded' and done.cancel_requested and done.charged_credits == 1
    assert adapter.submit_count == 0 and balances(env).wallet.available == 99


def test_queue_cancel_confirmation_refunds_only_after_provider_confirms_removal(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    def request_cancel(_):
        service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    adapter = FakeAdapter(draft, statuses=[FalStatus('IN_QUEUE'),
        FalRequestMissing('provider_request_missing')], on_submit=request_cancel)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    assert service.get(users[0].bearer, job.id).status == 'cancelled'
    assert adapter.cancel_count == 1 and balances(env).wallet.available == 100


def test_queue_cancel_202_can_race_into_progress_and_must_not_refund(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    def request_cancel(_):
        service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    adapter = FakeAdapter(draft, statuses=[FalStatus('IN_QUEUE'), FalStatus('IN_PROGRESS'),
                                          FalStatus('COMPLETED')], on_submit=request_cancel)
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    done = service.get(users[0].bearer, job.id)
    assert done.status == 'succeeded' and done.cancel_requested and done.charged_credits == 1
    assert adapter.cancel_count == 1 and balances(env).wallet.available == 99


def test_in_progress_cancel_can_still_complete_and_settle_without_false_refund(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    adapter = FakeAdapter(draft, statuses=[FalStatus('IN_PROGRESS'), FalStatus('IN_PROGRESS'), FalStatus('COMPLETED')])
    def late_cancel(count):
        if count == 1:
            service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    adapter.on_status = late_cancel
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    done = service.get(users[0].bearer, job.id)
    assert done.status == 'succeeded' and done.cancel_requested and done.charged_credits == 1
    assert adapter.cancel_count == 1



def test_expired_new_provider_job_is_never_submitted(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    clock[0] += 901
    assert runner.claim(resume_external=True) is None
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'failed' and result.error_code == 'admission_expired'
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
    assert recovered.status == 'queued' and recovered.error_code is None
    with service.auth.engine.connect() as conn:
        call = conn.execute(sa.select(j.provider_calls).where(j.provider_calls.c.job_id == job.id)).mappings().one()
        assert call['provider_request_id'] == 'request_12345678'
    assert first.submit_count == 1 and balances(env).wallet.reserved == 1
    resumed = FakeAdapter(draft)
    FalJobExecutor(runner, resumed, sleeper=lambda _: None).execute(runner.claim(resume_external=True))
    assert resumed.submit_count == 0
    assert service.get(users[0].bearer, job.id).status == 'succeeded'
    assert balances(env).wallet.available == 99


def test_known_provider_request_resumes_even_after_account_restriction(env):
    service, runner, users, clock, _, _, draft, job = create_provider(env)
    claim = runner.claim()
    runner.start(claim)
    base = 'https://queue.fal.run/fal-ai/flux-2/klein/4b/requests/request_restricted'
    with service.auth.engine.begin() as conn:
        conn.execute(sa.insert(j.provider_calls).values(id=uuid4(), job_id=job.id, provider='fal',
            connection_id='fal-klein-4b-v1', credential_ref='env:IZO_FAL_KEY:v1',
            provider_request_id='request_restricted', status_url=base+'/status', response_url=base,
            cancel_url=base+'/cancel', state='accepted', estimated_cost_microusd=21,
            reported_cost_microusd=None, last_error_code=None, created_at=clock[0], updated_at=clock[0]))
        conn.execute(sa.update(a.accounts).where(a.accounts.c.id == users[0].view.account.id)
                     .values(state='generation_suspended'))
    clock[0] += 31
    assert recover_fal(runner) == 1
    resumed = runner.claim(resume_external=True)
    assert resumed is not None
    FalJobExecutor(runner, FakeAdapter(draft), sleeper=lambda _: None).execute(resumed)
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'succeeded' and result.charged_credits == 1
    assert balances(env).wallet.available == 99


def test_account_restriction_after_provider_acceptance_does_not_create_false_refund(env):
    service, runner, users, _, _, _, draft, job = create_provider(env)
    adapter = FakeAdapter(draft, statuses=[FalStatus('COMPLETED')])
    def restrict_after_submit(count):
        if count == 1:
            with service.auth.engine.begin() as conn:
                conn.execute(sa.update(a.accounts).where(a.accounts.c.id == users[0].view.account.id)
                             .values(state='generation_suspended'))
    adapter.on_status = restrict_after_submit
    FalJobExecutor(runner, adapter, sleeper=lambda _: None).execute(runner.claim())
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'succeeded' and result.charged_credits == 1
    assert balances(env).wallet.available == 99 and balances(env).wallet.reserved == 0

def test_provider_migration_is_forward_only_and_has_no_application_imports():
    path = ROOT/'apps/api/migrations/versions/0009_provider_calls.py'
    tree = ast.parse(path.read_text())
    assert not any(isinstance(node, ast.ImportFrom) and 'izo' in (node.module or '') for node in ast.walk(tree))
    text = path.read_text()
    assert 'down_revision = "0008_jobs"' in text and 'generation_provider_calls' in text
    assert 'raise RuntimeError' in text


def test_fal_worker_secret_scope_and_egress_are_isolated_to_provider_service():
    compose = (ROOT/'compose.yaml').read_text()
    assert sum(line.lstrip().startswith('IZO_FAL_KEY:') for line in compose.splitlines()) == 1
    assert 'command: [python, \'-m\', izo.jobs.fal_worker]' in compose
    fal = compose[compose.index('  fal-worker:'):compose.index('  web:')]
    api = compose[compose.index('  api:'):compose.index('  job-worker:')]
    assert 'provider-egress' in fal and 'IZO_FAL_KEY' in fal
    assert 'provider-egress' not in api and 'IZO_FAL_KEY' not in api
