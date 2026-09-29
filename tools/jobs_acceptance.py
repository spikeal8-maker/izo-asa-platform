"""Explicit disposable PostgreSQL/S3 acceptance; stdout fixtures stay in RUNNER_TEMP."""
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import sqlalchemy as sa
from media_acceptance import checked, command as upload_intent, pixels
from jobs_access_acceptance import check_model_access_change
from izo.config import Settings
from izo.accounts import tables as a
from izo.accounts.repository import create_auth_engine
from izo.accounts.schemas import RegisterInput
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.credits.service import CreditService
from izo.credits.schemas import Grant
from izo.entitlements import tables as plans
from izo.entitlements.schemas import AssignPlan, PlanPolicy, ImageSize, PublishPlan
from izo.entitlements.service import EntitlementService
from izo.media.objects import MediaStore
from izo.media.service import MediaService
from izo.media.schemas import MediaError
from izo.jobs import tables as j
from izo.jobs.catalog import JobSettings, output_bound
from izo.jobs.schemas import QuoteInput, CreateJob, Claim, JobError
from izo.jobs.service import JobService
from izo.jobs.execution import JobRunner
from izo.jobs.worker import render_test_image

DRAFT = dict(capability_id='test.image.v1', prompt='isolated diagnostic image', width=64, height=64)


def fixture(auth):
    users = []
    for _ in range(3):
        receipt = auth.register(RegisterInput(email=f'job-{uuid4().hex}@example.invalid',
            display_name='Isolated job fixture', password=secrets.token_urlsafe(24),
            invite_code=auth.issue_invite()), 'isolated-jobs-' + uuid4().hex, 'job-acceptance')
        users.append({'id':str(receipt.view.account.id), 'bearer':receipt.bearer, 'csrf':receipt.view.csrf_token})
    actor = UUID(users[0]['id'])
    with auth.engine.begin() as conn:
        conn.execute(sa.update(a.identities).where(a.identities.c.account_id.in_(
            [UUID(user['id']) for user in users])).values(verified_at=auth.now()))
        conn.execute(sa.insert(a.permissions), [{'account_id':actor,'permission':x}
            for x in ('plans.write','credits.grant')])
        version = conn.execute(sa.select(sa.func.coalesce(sa.func.max(plans.revisions.c.revision),0))
            .where(plans.revisions.c.plan_code == 'custom')).scalar_one()
        for n, user in enumerate(users):
            revision_id = uuid4()
            policy = PlanPolicy(capability_ids=('test.image.v1',), executors=('api',),
                active_jobs=1 if n == 1 else 4, submissions=30, window_seconds=60,
                storage_bytes=output_bound(64,64) if n == 1 else 5_000_000,
                upload_bytes=1000, input_count=1, image_sizes=(ImageSize(width=64,height=64),),
                max_action_credits=1)
            svc = EntitlementService(clock=auth.clock)
            svc.publish(conn, actor, PublishPlan(operation_id=uuid4(), revision_id=revision_id,
                plan_code='custom', revision=version+n+1, policy=policy, reason='isolated job fixture'))
            svc.assign(conn, actor, UUID(user['id']), AssignPlan(operation_id=uuid4(), revision_id=revision_id,
                expected_version=0, starts_at=auth.now(), reason='isolated job fixture'))
            CreditService(clock=auth.clock).grant(conn, UUID(user['id']), actor,
                Grant(operation_id=uuid4(), case_id=uuid4(), amount=1 if n == 1 else 100,
                      reason='test_grant'), grant_limit=100)
    return users


def race(functions):
    gate = Barrier(len(functions))
    def call(fn):
        gate.wait(timeout=10)
        try:
            return fn()
        except (JobError, MediaError) as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(call, functions))


def quote(auth, user):
    result = checked(auth, user, '/api/v1/jobs/quotes', DRAFT, expected=201)
    assert result['test_only'] and result['credits'] == 1
    return CreateJob(quote_id=UUID(result['id']), operation_id=uuid4())


def submit(auth, user):
    command = quote(auth, user)
    result = checked(auth, user, '/api/v1/jobs', command.model_dump(mode='json'), expected=201)
    return result, command


def worker_process():
    # A separate server-side process, not browser state or the request handler.
    subprocess.run([sys.executable, '-m', 'izo.jobs.worker', '--once',
        '--worker-id', 'acceptance-process'], check=True, timeout=45,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def before(auth, config):
    users = fixture(auth)
    owner, limited, other = users
    service = JobService(auth, JobSettings(enabled=True))
    store = MediaStore(config)
    check_model_access_change(auth, store, owner, other)
    command = quote(auth, owner)
    pair = race([lambda: service.submit(owner['bearer'], owner['csrf'], command)] * 2)
    assert pair[0].id == pair[1].id, 'submission replay race'
    first_id = pair[0].id
    runners = [JobRunner(service, store, f'claim-racer-{n}') for n in range(2)]
    claimed = race([r.claim for r in runners])
    claims = [value for value in claimed if isinstance(value, Claim)]
    assert len(claims) == 1 and claims[0].job_id == first_id, 'single lease per job'
    runners[0].execute(claims[0], render_test_image)
    first = checked(auth, owner, '/api/v1/jobs/' + str(first_id))
    assert first['status'] == 'succeeded'
    checked(auth, other, '/api/v1/jobs/' + str(first_id), expected=404)
    ticket = checked(auth, owner, '/api/v1/media/assets/' + first['asset_id'] + '/download', {})
    assert checked(auth, owner, ticket['url']).startswith(b'\x89PNG')
    checked(auth, other, ticket['url'], expected=404)

    two = [quote(auth, limited), quote(auth, limited)]
    admission = race([lambda cmd=cmd: service.submit(limited['bearer'], limited['csrf'], cmd) for cmd in two])
    accepted = [r for r in admission if not isinstance(r,str)]
    assert len(accepted) == 1 and 'concurrency_limit' in admission
    service.cancel(limited['bearer'], limited['csrf'], accepted[0].id)
    pending = quote(auth, limited)
    media = MediaService(auth, store)
    competing = race([lambda: service.submit(limited['bearer'], limited['csrf'], pending),
        lambda: media.begin(limited['bearer'], limited['csrf'], upload_intent(pixels()))])
    assert sum(isinstance(r,str) for r in competing) == 1 and 'storage_quota_exceeded' in competing
    for n,r in enumerate(competing):
        if not isinstance(r,str):
            (service.cancel if n == 0 else media.cancel)(limited['bearer'], limited['csrf'], r.id)

    failed, _ = submit(auth, owner)
    runner = JobRunner(service, store)
    def broken(_):
        raise RuntimeError('synthetic executor failure')
    runner.execute(runner.claim(), broken)
    assert service.get(owner['bearer'], UUID(failed['id'])).status == 'failed'
    separate, _ = submit(auth, owner)
    worker_process()
    assert service.get(owner['bearer'], UUID(separate['id'])).status == 'succeeded'

    uncertain, _ = submit(auth, owner)
    class LostReply:
        def put(self, key, data, kind):
            store.put(key, data, kind)
            raise OSError('simulated reply loss after real object write')
        def read(self, key, maximum):
            return store.read(key, maximum)
    writer = JobRunner(service, LostReply())
    writer.execute(writer.claim(), render_test_image)
    assert service.get(owner['bearer'], UUID(uncertain['id'])).status == 'reconciling'
    pending_job, _ = submit(auth, other)
    old_claim = runner.claim()
    assert str(old_claim.job_id) == pending_job['id']
    # Explicit crash fixture: no output was produced by this claimed attempt.
    with auth.engine.begin() as conn:
        conn.execute(sa.update(j.jobs).where(j.jobs.c.id == old_claim.job_id)
                     .values(lease_until=auth.now()-1))
    print(json.dumps({'users':users, 'first_command':command.model_dump(mode='json'),
        'first':first, 'uncertain':uncertain['id'], 'pending':pending_job['id'],
        'old_claim':{'job_id':str(old_claim.job_id),'account_id':str(old_claim.account_id),
                     'attempt_id':str(old_claim.attempt_id),'fence':old_claim.fence}}))
    print('JOBS_BEFORE_OK: PG admission/replay/claim/quota races, real worker process, failed-job isolation and uncertain S3 write', file=sys.stderr)


def after(auth, config):
    state = json.loads(sys.stdin.read(65536))
    owner, _, other = state['users']
    service = JobService(auth, JobSettings(enabled=True))
    assert service.get(owner['bearer'], UUID(state['uncertain'])).status == 'reconciling'
    assert service.get(other['bearer'], UUID(state['pending'])).status == 'claimed'
    worker_process()  # Reconcile the saved image, recover and process the expired claim.
    for user, job_id in ((owner,state['uncertain']),(other,state['pending'])):
        job = checked(auth, user, '/api/v1/jobs/' + job_id)
        assert job['status'] == 'succeeded' and job['charged_credits'] == 1
        ticket = checked(auth, user, '/api/v1/media/assets/' + job['asset_id'] + '/download', {})
        assert checked(auth, user, ticket['url']).startswith(b'\x89PNG')
    replay = checked(auth, owner, '/api/v1/jobs', state['first_command'], expected=201)
    assert replay['id'] == state['first']['id'] and replay['status'] == 'succeeded'
    claim = state['old_claim']
    stale = Claim(UUID(claim['job_id']),UUID(claim['account_id']),UUID(claim['attempt_id']),claim['fence'])
    try:
        JobRunner(service,MediaStore(config)).start(stale)
    except JobError as exc:
        assert exc.code == 'stale_attempt'
    else:
        raise AssertionError('Stale worker was accepted')
    for n,user in enumerate(state['users']):
        with auth.engine.begin() as conn:
            audit = CreditService(clock=auth.clock).reconcile(conn,UUID(user['id']))
            charged = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(j.jobs.c.charged_credits),0))
                .where(j.jobs.c.account_id == UUID(user['id']))).scalar_one()
            assert audit.consistent and audit.wallet.reserved == 0
            assert audit.wallet.balance == (1 if n == 1 else 100) - charged
    print('JOBS_AFTER_OK: durable jobs/holds/results across Compose restart; saved output reconciled; expired claim recovered; stale token denied; credits consistent')


def main():
    if (os.environ.get('IZO_JOBS_ACCEPTANCE') != 'isolated'
            or os.environ.get('IZO_ENVIRONMENT') != 'test' or not JobSettings().enabled):
        raise SystemExit('Explicit isolated job acceptance only')
    if len(sys.argv) != 2 or sys.argv[1] not in {'before','after'}:
        raise SystemExit('Use before or after')
    config = Settings()
    if config.pg_host != 'postgres' or config.s3_endpoint != 'http://storage:8333':
        raise SystemExit('Standard disposable Compose dependencies required')
    engine = create_auth_engine(config)
    try:
        auth = AuthService(engine, AuthSettings())
        before(auth, config) if sys.argv[1] == 'before' else after(auth, config)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
