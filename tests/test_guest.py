"""GUEST-001 domain lifecycle: bounded anonymous principal, one trial and same-owner claim."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import guest_tables as guest_tables, tables as accounts
from izo.accounts.guest_service import GuestService
from izo.accounts.guest_settings import GuestSettings
from izo.accounts.schemas import RegisterInput
from izo.accounts.security import AuthError
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.credits.service import CreditService
from izo.credits.trial import seed_guest_trial
from izo.entitlements import tables as entitlements
from izo.entitlements.schemas import ImageSize, PlanPolicy, PublishPlan, SetDefault
from izo.entitlements.service import EntitlementService
from izo.jobs import tables as jobs
from izo.jobs.catalog import JobSettings
from izo.jobs.execution import JobRunner
from izo.jobs.schemas import ACTIVE, CreateJob, QuoteInput
from izo.jobs.service import JobService
from izo.jobs.worker import render_test_image
from izo.media import codec, tables as media
from izo.media.service import MediaService
from test_media import MemoryStore


@pytest.fixture
def guest_env(tmp_path, monkeypatch):
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'guest.sqlite'),
                              connect_args={'check_same_thread': False})
    @sa.event.listens_for(engine, 'connect')
    def connect(db, _):
        db.isolation_level = None
        db.execute('PRAGMA foreign_keys=ON')
    @sa.event.listens_for(engine, 'begin')
    def begin(conn):
        conn.exec_driver_sql('BEGIN')

    accounts.metadata.create_all(engine)
    media.metadata.create_all(engine, tables=list(media.TABLES))
    jobs.metadata.create_all(engine, tables=list(jobs.TABLES))
    clock = [10_000]
    auth = AuthService(engine, AuthSettings(registration='open', rate_secret='x' * 40,
        login_limit=100, network_limit=1000), clock=lambda: clock[0])
    operator = auth.register(RegisterInput(email='guest-operator@example.invalid',
        display_name='Operator', password='synthetic-password-only'), 'isolated', 'test')
    with engine.begin() as conn:
        conn.execute(sa.update(accounts.identities).where(
            accounts.identities.c.account_id == operator.view.account.id).values(verified_at=clock[0]))
        conn.execute(sa.insert(accounts.permissions).values(
            account_id=operator.view.account.id, permission='plans.write'))
        conn.execute(sa.insert(entitlements.defaults).values(id=1, version=0))
        revision = uuid4()
        plans = EntitlementService(clock=auth.clock)
        plans.publish(conn, operator.view.account.id, PublishPlan(operation_id=uuid4(),
            reason='guest fixture', revision_id=revision, plan_code='basic', revision=1,
            policy=PlanPolicy(capability_ids=('test.image.v1',), executors=('api',), active_jobs=4,
                submissions=20, window_seconds=60, storage_bytes=5_000_000,
                upload_bytes=1_000_000, input_count=4,
                image_sizes=(ImageSize(width=64, height=64),), max_action_credits=1)))
        plans.set_default(conn, operator.view.account.id, SetDefault(operation_id=uuid4(),
            reason='guest fixture', revision_id=revision, expected_version=0))

    settings = GuestSettings(enabled=True, session_seconds=600, network_limit=3,
                             rate_window=3600, trial_credits=3)
    guest = GuestService(auth, settings)
    receipt = guest.start('guest-peer', 'test', initializer=lambda conn, owner, now:
        seed_guest_trial(conn, owner, settings.trial_credits, now))
    service = JobService(guest, JobSettings(enabled=True), admission_guard=guest.admission_guard)
    store = MemoryStore()
    monkeypatch.setattr(codec, 'decode', codec.rewrite)
    runner = JobRunner(service, store)
    yield auth, guest, receipt, service, runner, clock, store
    engine.dispose()


def draft():
    return QuoteInput(capability_id='test.image.v1', prompt='guest trial', width=64, height=64)


def create_job(env):
    _, _, receipt, service, *_ = env
    quote = service.quote(receipt.bearer, receipt.view.csrf_token, draft())
    command = CreateJob(quote_id=quote.id, operation_id=uuid4())
    return service.submit(receipt.bearer, receipt.view.csrf_token, command), command


def claim_guard(conn, account_id):
    active = conn.execute(sa.select(jobs.jobs.c.id).where(
        jobs.jobs.c.account_id == account_id, jobs.jobs.c.status.in_(ACTIVE)).limit(1)).first()
    if active is not None:
        raise AuthError(409, 'guest_job_active')


def test_guest_bearer_is_not_normal_auth_and_trial_is_auditable(guest_env):
    auth, guest, receipt, *_ = guest_env
    with pytest.raises(AuthError, match='auth_required'):
        auth.me(receipt.bearer)
    assert guest.me(receipt.bearer).account_id == receipt.view.account_id
    with auth.engine.begin() as conn:
        state = CreditService(clock=auth.clock).reconcile(conn, receipt.view.account_id)
        entries = conn.execute(sa.select(sa.text('kind'), sa.text('reason')).select_from(
            sa.table('credit_ledger')).where(sa.text('account_id = :owner')),
            {'owner': receipt.view.account_id}).all()
    assert state.consistent and state.wallet.balance == 3 and state.wallet.available == 3
    assert entries == [('trial', 'guest_trial')]


def test_exact_replay_is_safe_but_second_guest_job_is_rejected(guest_env):
    _, _, receipt, service, *_ = guest_env
    job, command = create_job(guest_env)
    assert service.submit(receipt.bearer, receipt.view.csrf_token, command).id == job.id
    second_quote = service.quote(receipt.bearer, receipt.view.csrf_token, draft())
    with pytest.raises(AuthError, match='guest_trial_used'):
        service.submit(receipt.bearer, receipt.view.csrf_token,
            CreateJob(quote_id=second_quote.id, operation_id=uuid4()))
    with service.auth.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(jobs.jobs)).scalar_one() == 1


def test_claim_waits_for_terminal_job_and_preserves_owner_asset(guest_env):
    auth, guest, receipt, service, runner, _, store = guest_env
    job, _ = create_job(guest_env)
    registration = RegisterInput(email='claimed-guest@example.invalid', display_name='Claimed user',
                                 password='synthetic-password-only')
    with pytest.raises(AuthError, match='guest_job_active'):
        guest.claim(receipt.bearer, receipt.view.csrf_token, registration,
                    'guest-peer', 'test', guard=claim_guard)

    worker_claim = runner.claim()
    assert worker_claim is not None
    runner.execute(worker_claim, render_test_image)
    result = service.get(receipt.bearer, job.id)
    assert result.status == 'succeeded' and result.asset_id is not None

    normal = guest.claim(receipt.bearer, receipt.view.csrf_token, registration,
                         'guest-peer', 'test', guard=claim_guard)
    assert normal.view.account.id == receipt.view.account_id
    assert normal.view.account.email == registration.email
    assert normal.view.account.email_verified is False
    with pytest.raises(AuthError, match='guest_required'):
        guest.me(receipt.bearer)
    assert auth.me(normal.bearer).account.id == receipt.view.account_id
    assets = MediaService(auth, store).list(normal.bearer).assets
    assert [asset.id for asset in assets] == [result.asset_id]


def test_guest_expiry_and_network_creation_limit_fail_closed(guest_env):
    auth, guest, receipt, _, _, clock, _ = guest_env
    clock[0] += guest.settings.session_seconds + 1
    with pytest.raises(AuthError, match='guest_required'):
        guest.me(receipt.bearer)

    limited = GuestService(auth, GuestSettings(enabled=True, session_seconds=600,
        network_limit=1, rate_window=3600, trial_credits=1))
    first = limited.start('limited-peer', 'test', initializer=lambda conn, owner, now:
        seed_guest_trial(conn, owner, 1, now))
    assert first.view.account_id
    with pytest.raises(AuthError, match='guest_rate_limited'):
        limited.start('limited-peer', 'test', initializer=lambda conn, owner, now:
            seed_guest_trial(conn, owner, 1, now))
