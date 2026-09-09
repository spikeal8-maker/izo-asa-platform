"""Disposable IMAGE-001 fixtures. Browser performs the grant and generation.

Only synthetic credentials go to protected RUNNER_TEMP; never artifact uploads.
No public provisioning endpoint, production account, external mail or AI call.
"""
import json
import os
import sys
from uuid import UUID, uuid4
import sqlalchemy as sa

from admin_acceptance import create_fixture, call
from auth_acceptance import Client, check
from izo.config import Settings
from izo.accounts import tables as a
from izo.accounts.repository import create_auth_engine
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.admin.service import AdminService
from izo.credits.service import CreditService
from izo.credits import tables as c
from izo.entitlements import tables as e
from izo.entitlements.service import EntitlementService
from izo.entitlements.schemas import PlanPolicy, ImageSize, PublishPlan, AssignPlan
from izo.jobs.catalog import JobSettings
from izo.jobs.service import JobService
from izo.jobs import tables as j
from izo.media import tables as m


def before(auth):
    _, operator = create_fixture(auth, 'Synthetic Image Operator')
    _, recipient = create_fixture(auth, 'Synthetic Image User')
    _, other = create_fixture(auth, 'Synthetic Image Other User')
    actor, owner = UUID(operator['id']), UUID(recipient['id'])
    AdminService(auth).enroll_local_operator(actor, 20)
    with auth.engine.begin() as conn:
        conn.execute(sa.insert(a.permissions).values(account_id=actor, permission='plans.write'))
        revision = conn.execute(sa.select(sa.func.coalesce(sa.func.max(e.revisions.c.revision), 0))
            .where(e.revisions.c.plan_code == 'custom')).scalar_one() + 1
        revision_id = uuid4()
        policy = PlanPolicy(capability_ids=('test.image.v1',), executors=('api',), active_jobs=2,
            submissions=30, window_seconds=60, storage_bytes=5_000_000, upload_bytes=0,
            image_sizes=(ImageSize(width=64, height=64), ImageSize(width=128, height=64)),
            max_action_credits=1)
        service = EntitlementService(clock=auth.clock)
        service.publish(conn, actor, PublishPlan(operation_id=uuid4(), revision_id=revision_id,
            plan_code='custom', revision=revision, policy=policy, reason='isolated browser image fixture'))
        service.assign(conn, actor, owner, AssignPlan(operation_id=uuid4(), revision_id=revision_id,
            expected_version=0, starts_at=auth.now(), reason='isolated browser image fixture'))
        check(CreditService(clock=auth.clock).overview(conn, owner).balance.available == 0, 'image_starts_without_credit')
    print('IMAGE_FIXTURE_OK: separate synthetic users and explicit plan; browser must grant and submit', file=sys.stderr)
    return {'operator': operator, 'recipient': recipient, 'other': other,
            'case': 'IMAGE-' + uuid4().hex, 'browser': None}


def after(auth, state):
    saved = state['browser']
    check(isinstance(saved, dict), 'real_browser_must_have_completed_before_restart')
    owner = UUID(state['recipient']['id'])
    job_id, asset_id = UUID(saved['job_id']), UUID(saved['asset_id'])
    service = JobService(auth, JobSettings(enabled=True))
    job = service.get(state['recipient']['raw'], job_id)
    check(job.status == 'succeeded' and job.asset_id == asset_id and job.charged_credits == 1, 'image_job_persisted')
    with auth.engine.begin() as conn:
        audit = CreditService(clock=auth.clock).reconcile(conn, owner)
        check(audit.consistent and audit.wallet.balance == 4 and audit.wallet.reserved == 0, 'image_ledger_consistent')
        kinds = conn.execute(sa.select(c.ledger.c.kind).where(c.ledger.c.account_id == owner)).scalars().all()
        check(sorted(kinds) == ['grant', 'reserve', 'settle'], 'one_browser_grant_and_settlement')
        check(conn.execute(sa.select(sa.func.count()).select_from(j.jobs).where(j.jobs.c.account_id == owner)).scalar_one() == 1,
              'one_browser_job')
        file = conn.execute(sa.select(m.assets).where(m.assets.c.id == asset_id, m.assets.c.account_id == owner)).mappings().one()
        check(file['sha256'] == saved['sha256'], 'same_saved_file_after_restart')
    other = Client(auth.policy.cookie_name, state['other']['raw']); other.csrf = state['other']['csrf']
    check(call(other, 'GET', 'jobs/' + str(job_id))[0] == 404, 'foreign_job_denied')
    check(call(other, 'GET', 'media/assets/' + str(asset_id))[0] == 404, 'foreign_asset_denied')
    print('IMAGE_AFTER_OK: real browser grant/job/asset persisted; single settlement and owner isolation after Compose restart')


def main():
    if (os.getenv('IZO_ENVIRONMENT') != 'test' or os.getenv('IZO_IMAGE_ACCEPTANCE') != 'isolated'
            or not JobSettings().enabled):
        raise SystemExit('Explicit isolated image acceptance only')
    config = Settings()
    if config.pg_host != 'postgres' or config.s3_endpoint != 'http://storage:8333':
        raise SystemExit('Disposable Compose dependencies required')
    engine = create_auth_engine(config)
    try:
        auth = AuthService(engine, AuthSettings())
        if sys.argv[1:] == ['before']:
            print(json.dumps(before(auth)))
        elif sys.argv[1:] == ['after']:
            after(auth, json.loads(sys.stdin.read(65536)))
        else:
            raise SystemExit('Expected before or after')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
