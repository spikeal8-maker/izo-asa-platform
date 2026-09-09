"""Real Accounts/Credits/Entitlements/Media transactions; no network or paid model."""
from uuid import uuid4
import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.accounts import tables as a
from izo.accounts.service import AuthService
from izo.accounts.schemas import RegisterInput
from izo.accounts.settings import AuthSettings
from izo.credits.schemas import Grant
from izo.credits.service import CreditService
from izo.entitlements import tables as e
from izo.entitlements.schemas import PlanPolicy, ImageSize, PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.media import tables as m, codec
from izo.media.service import MediaService
from izo.jobs import tables as j, repository as repo
from izo.jobs.catalog import JobSettings
from izo.jobs.schemas import QuoteInput, CreateJob, JobError
from izo.jobs.service import JobService
from izo.jobs.execution import JobRunner
from izo.jobs.worker import render_test_image
from test_media import MemoryStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = sa.create_engine('sqlite:///' + str(tmp_path/'jobs.sqlite'), connect_args={'check_same_thread': False})
    @sa.event.listens_for(engine, 'connect')
    def connect(db, _):
        db.isolation_level = None
        db.execute('PRAGMA foreign_keys=ON')
    @sa.event.listens_for(engine, 'begin')
    def begin(conn):
        conn.exec_driver_sql('BEGIN')
    a.metadata.create_all(engine)
    m.metadata.create_all(engine, tables=list(m.TABLES))
    j.metadata.create_all(engine, tables=list(j.TABLES))
    clock = [2000]
    auth = AuthService(engine, AuthSettings(registration='invite', rate_secret='x'*40,
        login_limit=100, network_limit=1000), clock=lambda: clock[0])
    users = [auth.register(RegisterInput(email=f'jobs-{n}@example.invalid',
        display_name='Synthetic jobs user', password='synthetic-password-only',
        invite_code=auth.issue_invite()), 'isolated', 'test') for n in range(2)]
    operator = users[0].view.account.id
    with engine.begin() as conn:
        conn.execute(sa.update(a.identities).values(verified_at=2000))
        conn.execute(sa.insert(a.permissions), [{'account_id': operator, 'permission': name}
            for name in ('plans.write', 'credits.grant')])
        conn.execute(sa.insert(e.defaults).values(id=1, version=0))
        plans = EntitlementService(clock=auth.clock)
        revision = uuid4()
        plans.publish(conn, operator, PublishPlan(operation_id=uuid4(), reason='isolated fixture',
            revision_id=revision, plan_code='basic', revision=1,
            policy=PlanPolicy(capability_ids=('test.image.v1',), executors=('api',), active_jobs=4,
                submissions=20, window_seconds=60, storage_bytes=5_000_000,
                upload_bytes=1_000_000, input_count=4, image_sizes=(ImageSize(width=64,height=64),),
                max_action_credits=1)))
        plans.set_default(conn, operator, SetDefault(operation_id=uuid4(), reason='isolated fixture',
            revision_id=revision, expected_version=0))
        for user in users:
            CreditService(clock=auth.clock).grant(conn, user.view.account.id, operator,
                Grant(operation_id=uuid4(), amount=100, case_id=uuid4(), reason='test_grant'), grant_limit=100)
    store = MemoryStore()
    monkeypatch.setattr(codec, 'decode', codec.rewrite)
    service = JobService(auth, JobSettings(enabled=True))
    runner = JobRunner(service, store)
    yield service, runner, users, clock, store
    engine.dispose()


def draft(**kwargs):
    return QuoteInput(**(dict(capability_id='test.image.v1', prompt='isolation test', width=64, height=64) | kwargs))


def create(env, user_index=0):
    service, _, users, *_ = env
    user = users[user_index]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    command = CreateJob(quote_id=quote.id, operation_id=uuid4())
    return service.submit(user.bearer, user.view.csrf_token, command), command


def balances(env, index=0):
    service, _, users, *_ = env
    with service.auth.engine.begin() as conn:
        return CreditService(clock=service.auth.clock).reconcile(conn, users[index].view.account.id)


def test_durable_admission_render_settle_and_common_media(env):
    service, runner, users, _, store = env
    job, command = create(env)
    assert job.status == 'queued' and job.reserved_credits == 1
    assert balances(env).wallet.available == 99 and balances(env).wallet.balance == 100
    claim = runner.claim()
    assert claim and runner.claim() is None
    runner.execute(claim, render_test_image)
    result = service.get(users[0].bearer, job.id)
    assert result.status == 'succeeded' and result.charged_credits == 1 and result.asset_id
    media = MediaService(service.auth, store)
    assert [item.id for item in media.list(users[0].bearer).assets] == [result.asset_id]
    assert not media.list(users[1].bearer).assets
    assert balances(env).consistent and balances(env).wallet.available == 99
    assert balances(env).wallet.reserved == 0
    assert service.submit(users[0].bearer, users[0].view.csrf_token, command).id == job.id
    assert len(store.data) == 1


def test_repeat_submission_never_reserves_twice_even_after_quote_expiry(env):
    service, _, users, clock, _ = env
    job, command = create(env)
    clock[0] += 121
    assert service.submit(users[0].bearer, users[0].view.csrf_token, command).id == job.id
    assert balances(env).wallet.reserved == 1
    with pytest.raises(JobError, match='idempotency_conflict'):
        service.submit(users[0].bearer, users[0].view.csrf_token,
            CreateJob(quote_id=uuid4(), operation_id=command.operation_id))


def test_quote_has_one_use_even_with_new_operation_key(env):
    service, _, users, *_ = env
    _, command = create(env)
    with pytest.raises(JobError, match='quote_already_used'):
        service.submit(users[0].bearer, users[0].view.csrf_token,
            CreateJob(quote_id=command.quote_id, operation_id=uuid4()))
    assert balances(env).wallet.reserved == 1


def test_quote_does_not_reserve_and_expires(env):
    service, _, users, clock, _ = env
    user = users[0]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    assert balances(env).wallet.available == 100
    clock[0] += 120
    with pytest.raises(JobError, match='quote_expired'):
        service.submit(user.bearer, user.view.csrf_token, CreateJob(quote_id=quote.id, operation_id=uuid4()))
    assert balances(env).wallet.reserved == 0


@pytest.mark.parametrize('failure_at', ['credit', 'job', 'outbox'])
def test_any_admission_failure_rolls_back_all_resources(env, monkeypatch, failure_at):
    service, _, users, *_ = env
    user = users[0]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    target = {'credit':'credit_ledger', 'job':'generation_jobs', 'outbox':'job_outbox'}[failure_at]
    def broken(conn, cursor, statement, params, context, many):
        if statement.startswith('INSERT INTO ' + target):
            raise RuntimeError('synthetic transaction failure')
    sa.event.listen(service.auth.engine, 'before_cursor_execute', broken)
    with pytest.raises(RuntimeError):
        service.submit(user.bearer, user.view.csrf_token, CreateJob(quote_id=quote.id, operation_id=uuid4()))
    sa.event.remove(service.auth.engine, 'before_cursor_execute', broken)
    assert balances(env).wallet.available == 100
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(m.outputs)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(j.jobs)).scalar_one() == 0


@pytest.mark.parametrize('state', ['queued','claimed','running'])
def test_cancel_before_sealing_releases_once_and_rejects_late_output(env, state):
    service, runner, users, *_ = env
    user = users[0]
    job, _ = create(env)
    claim = runner.claim() if state != 'queued' else None
    if state == 'running':
        runner.start(claim)
    assert service.cancel(user.bearer, user.view.csrf_token, job.id).status == 'cancelled'
    assert service.cancel(user.bearer, user.view.csrf_token, job.id).status == 'cancelled'
    if claim:
        runner.execute(claim, render_test_image)
    assert balances(env).consistent and balances(env).wallet.available == 100
    assert not service.list(users[1].bearer).jobs


def test_failed_job_does_not_stop_next_job(env):
    service, runner, users, *_ = env
    first, _ = create(env)
    claim = runner.claim()
    def broken(_):
        raise RuntimeError('private provider details')
    runner.execute(claim, broken)
    assert service.get(users[0].bearer, first.id).status == 'failed'
    second, _ = create(env)
    runner.execute(runner.claim(), render_test_image)
    assert service.get(users[0].bearer, second.id).status == 'succeeded'
    assert balances(env).wallet.available == 99


@pytest.mark.parametrize('field,value', [('owner_id','claimed'),('reserve_credits',0),('executor','local'),('url','https://wrong.invalid'),('width',True),('width',513),('height',0),('prompt','   ')])
def test_public_input_cannot_set_internal_fields(field,value):
    with pytest.raises(ValidationError):
        draft(**{field:value})


def test_admission_rechecks_usage_after_quote(env):
    service, _, users, *_ = env
    user = users[0]
    quotes = [service.quote(user.bearer, user.view.csrf_token, draft()) for _ in range(5)]
    for quote in quotes[:4]:
        service.submit(user.bearer, user.view.csrf_token, CreateJob(quote_id=quote.id, operation_id=uuid4()))
    with pytest.raises(JobError, match='concurrency_limit'):
        service.submit(user.bearer, user.view.csrf_token, CreateJob(quote_id=quotes[4].id, operation_id=uuid4()))
    assert balances(env).wallet.reserved == 4


def test_owner_privacy_and_disabled_mode(env):
    service, _, users, *_ = env
    job, _ = create(env)
    with pytest.raises(JobError, match='not_found'):
        service.get(users[1].bearer, job.id)
    with pytest.raises(JobError, match='not_found'):
        service.cancel(users[1].bearer, users[1].view.csrf_token, job.id)
    disabled = JobService(service.auth, JobSettings(enabled=False))
    assert disabled.get(users[0].bearer, job.id).id == job.id
    with pytest.raises(JobError, match='jobs_disabled'):
        disabled.quote(users[0].bearer, users[0].view.csrf_token, draft())


def test_changed_quote_price_is_rejected_without_hold(env):
    service, _, users, *_ = env
    user = users[0]
    quote = service.quote(user.bearer, user.view.csrf_token, draft())
    with service.auth.engine.begin() as conn:
        conn.execute(sa.update(j.quotes).where(j.quotes.c.id == quote.id).values(credits=2))
    with pytest.raises(JobError, match='quote_expired'):
        service.submit(user.bearer, user.view.csrf_token,
                       CreateJob(quote_id=quote.id, operation_id=uuid4()))
    assert balances(env).wallet.reserved == 0
