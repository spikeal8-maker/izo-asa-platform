"""Lease/fencing, cancel races, uncertain S3 writes and all-or-nothing settlement."""
from uuid import uuid4
import pytest
import sqlalchemy as sa

from izo.accounts import tables as a
from izo.jobs import tables as j
from izo.jobs.schemas import JobError, CreateJob
from izo.jobs.execution import JobRunner
from izo.jobs.recovery import recover, reconcile_one
from izo.jobs.service import JobService
from izo.jobs.worker import render_test_image
from izo.media import tables as m, codec
from izo.media.service import MediaService
from izo.media.schemas import MediaError
from izo.entitlements.service import EntitlementService
from izo.entitlements.schemas import PublishPlan, SetDefault
from test_jobs import env, create, balances, draft
from test_media import image_bytes, intent


def seal(env, claim):
    service, runner, *_ = env
    spec = runner.start(claim)
    image = codec.rewrite(render_test_image(spec), 'image/png', spec.width, spec.height, 1_000_000)
    return runner.seal(claim, image), image.data


@pytest.mark.parametrize('phase', ['claimed','running'])
def test_expired_test_attempt_requeues_with_new_fence(env, phase):
    service, runner, users, clock, _ = env
    job, _ = create(env)
    old = runner.claim()
    if phase == 'running':
        runner.start(old)
    clock[0] += 31
    assert recover(runner) == 1
    new = runner.claim()
    assert new.job_id == old.job_id and new.fence == old.fence + 1
    with pytest.raises(JobError, match='stale_attempt'):
        runner.start(old)
    runner.execute(new, render_test_image)
    assert service.get(users[0].bearer, job.id).status == 'succeeded'
    assert balances(env).consistent and balances(env).wallet.available == 99


def test_heartbeat_prevents_early_reclaim_but_cannot_resurrect_expired_lease(env):
    service, runner, users, clock, _ = env
    create(env)
    claim = runner.claim()
    clock[0] += 20
    runner.heartbeat(claim)
    clock[0] += 20
    assert recover(runner) == 0
    clock[0] += 11
    with pytest.raises(JobError, match='lease_expired'):
        runner.heartbeat(claim)
    assert recover(runner) == 1


def test_attempt_retry_is_finite_and_releases_all_holds(env):
    service, runner, users, clock, _ = env
    job, _ = create(env)
    for _ in range(3):
        assert runner.claim() is not None
        clock[0] += 31
        recover(runner)
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'failed' and result.attempt_count == 3
    assert balances(env).wallet.available == 100
    assert runner.claim() is None


def test_queued_deadline_does_not_leave_an_eternal_reservation(env):
    service, runner, users, clock, _ = env
    job, _ = create(env)
    clock[0] += 901
    assert recover(runner) == 1
    assert service.get(users[0].bearer, job.id).status == 'failed'
    assert balances(env).wallet.reserved == 0


def test_uncertain_successful_storage_is_recovered_without_regenerating(env):
    service, runner, users, _, store = env
    job, _ = create(env)
    store.failure = 'after'
    calls = []
    def render(spec):
        calls.append(spec)
        return render_test_image(spec)
    runner.execute(runner.claim(), render)
    assert service.get(users[0].bearer, job.id).status == 'reconciling'
    assert balances(env).wallet.reserved == 1
    # A new runner has no in-memory job state.
    store.failure = None
    fresh = JobRunner(JobService(service.auth, service.policy), store, 'replacement')
    assert reconcile_one(fresh)
    assert not reconcile_one(fresh)
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'succeeded' and len(calls) == 1
    assert len(store.data) == 1 and balances(env).wallet.available == 99
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.assets)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(j.outbox).where(
            j.outbox.c.event_type == 'succeeded')).scalar_one() == 1


def test_missing_uncertain_object_has_bounded_polling_and_keeps_liability(env):
    service, runner, users, clock, store = env
    job, _ = create(env)
    store.failure = 'before'
    runner.execute(runner.claim(), render_test_image)
    for _ in range(5):
        assert reconcile_one(runner)
        clock[0] += 301
    assert not reconcile_one(runner)
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'reconciling' and result.error_code == 'reconciliation_required'
    assert balances(env).wallet.reserved == 1 and len(store.data) == 0
    assert runner.claim() is None  # never a second rendering request


def test_cancel_after_sealing_is_a_request_not_a_false_refund(env):
    service, runner, users, _, store = env
    job, _ = create(env)
    claim = runner.claim()
    key, data = seal(env, claim)
    cancelled = service.cancel(users[0].bearer, users[0].view.csrf_token, job.id)
    assert cancelled.status == 'uploading' and cancelled.cancel_requested
    assert balances(env).wallet.reserved == 1
    store.put(key, data, 'image/png')
    done = runner.finish(claim, data)
    assert done.status == 'succeeded' and done.cancel_requested
    assert runner.finish(claim, data) == done
    assert balances(env).wallet.available == 99


def test_late_old_completion_cannot_overwrite_recovered_attempt(env):
    service, runner, users, clock, store = env
    job, _ = create(env)
    old = runner.claim()
    key, data = seal(env, old)
    store.put(key, data, 'image/png')
    clock[0] += 31
    assert recover(runner) == 1 and reconcile_one(runner)
    with pytest.raises(JobError, match='stale_attempt'):
        runner.finish(old, data)
    assert service.get(users[0].bearer, job.id).status == 'succeeded'
    assert balances(env).wallet.available == 99


def test_settlement_event_failure_rolls_back_asset_and_debit(env):
    service, runner, users, _, store = env
    job, _ = create(env)
    claim = runner.claim()
    key, data = seal(env, claim)
    store.put(key, data, 'image/png')
    def broken(conn, cursor, statement, params, context, many):
        if statement.startswith('INSERT INTO job_outbox'):
            raise RuntimeError('synthetic outbox failure')
    sa.event.listen(service.auth.engine, 'before_cursor_execute', broken)
    with pytest.raises(RuntimeError):
        runner.finish(claim, data)
    sa.event.remove(service.auth.engine, 'before_cursor_execute', broken)
    assert balances(env).wallet.balance == 100 and balances(env).wallet.reserved == 1
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.assets)).scalar_one() == 0
    assert runner.finish(claim, data).status == 'succeeded'


@pytest.mark.parametrize('state', ['generation_suspended','security_locked','deletion_pending','deleted'])
def test_restricted_owner_is_not_dispatched_and_hold_is_released(env, state):
    service, runner, users, *_ = env
    job, _ = create(env)
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(a.accounts).where(a.accounts.c.id == users[0].view.account.id).values(state=state))
    assert runner.claim() is None
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(j.jobs.c.status).where(j.jobs.c.id == job.id)).scalar_one() == 'failed'
    assert balances(env).wallet.reserved == 0


def smaller_plan(env):
    service, _, users, *_ = env
    owner = users[0].view.account.id
    plans = EntitlementService(clock=service.auth.clock)
    with service.auth.engine.begin() as conn:
        previous = plans.resolve(conn, owner)
        policy = previous.policy.model_copy(update={'storage_bytes': 90000, 'upload_bytes': 32000})
        revision = uuid4()
        plans.publish(conn, owner, PublishPlan(operation_id=uuid4(), revision_id=revision,
            plan_code='basic', revision=2, reason='quota race fixture', policy=policy))
        plans.set_default(conn, owner, SetDefault(operation_id=uuid4(), revision_id=revision,
            expected_version=previous.default_version, reason='quota race fixture'))


def test_upload_reservation_between_quote_and_submit_blocks_job(env):
    service, _, users, _, store = env
    smaller_plan(env)
    user = users[0]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    media = MediaService(service.auth, store)
    media.begin(user.bearer, user.view.csrf_token, intent(image_bytes()))
    with pytest.raises(JobError, match='storage_quota_exceeded'):
        service.submit(user.bearer, user.view.csrf_token, CreateJob(quote_id=quote.id, operation_id=uuid4()))
    assert balances(env).wallet.reserved == 0


def test_admitted_job_reserves_space_against_later_upload(env):
    service, _, users, _, store = env
    smaller_plan(env)
    create(env)
    media = MediaService(service.auth, store)
    with pytest.raises(MediaError, match='storage_quota_exceeded'):
        media.begin(users[0].bearer, users[0].view.csrf_token, intent(image_bytes()))
    assert balances(env).wallet.reserved == 1


def test_heartbeat_cannot_extend_past_job_deadline(env):
    service, runner, _, clock, _ = env
    job, _ = create(env)
    claim = runner.claim()
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(j.jobs).where(j.jobs.c.id == job.id).values(deadline_at=clock[0]+5))
    runner.heartbeat(claim)
    clock[0] += 6
    with pytest.raises(JobError, match='lease_expired'):
        runner.heartbeat(claim)
    assert recover(runner) == 1
    assert balances(env).wallet.reserved == 0


def test_expired_unwritten_upload_no_longer_blocks_job_space(env):
    service, _, users, clock, store = env
    owner = users[0]
    media = MediaService(service.auth, store)
    upload = media.begin(owner.bearer, owner.view.csrf_token, intent(image_bytes()))
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(m.uploads).where(m.uploads.c.id == upload.id)
                     .values(expires_at=clock[0]+1))
    clock[0] += 2
    create(env)
    with service.auth.engine.begin() as conn:
        row = conn.execute(sa.select(m.uploads).where(m.uploads.c.id == upload.id)).mappings().one()
        assert row['status'] == 'expired' and row['reserved_bytes'] == 0
