"""Isolated PostgreSQL/S3 acceptance for GUEST-001 before and after Compose restart."""
import json
import os
import sys
from uuid import UUID, uuid4

import sqlalchemy as sa

from izo.accounts.guest_service import GuestService
from izo.accounts.guest_settings import GuestSettings
from izo.accounts.repository import create_auth_engine
from izo.accounts.schemas import RegisterInput
from izo.accounts.security import AuthError
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.config import Settings
from izo.credits.service import CreditService
from izo.credits.trial import seed_guest_trial
from izo.guest.media import read_owned
from izo.jobs import tables as jt
from izo.jobs.catalog import JobSettings
from izo.jobs.execution import JobRunner
from izo.jobs.schemas import ACTIVE, CreateJob, QuoteInput
from izo.jobs.service import JobService
from izo.jobs.worker import render_test_image
from izo.media.objects import MediaStore
from izo.media.service import MediaService

CLAIM_PASSWORD = "guest-acceptance-only-password"


def services():
    if os.environ.get("IZO_ENVIRONMENT") != "test" or os.environ.get("IZO_GUEST_ACCEPTANCE") != "isolated":
        raise SystemExit("isolated guest acceptance environment required")
    config = Settings()
    auth = AuthService(create_auth_engine(config), AuthSettings())
    guest = GuestService(auth, GuestSettings())
    jobs = JobService(guest, JobSettings(), admission_guard=guest.admission_guard)
    store = MediaStore(config)
    return auth, guest, jobs, store


def no_active(conn, account_id):
    active = conn.execute(sa.select(jt.jobs.c.id).where(
        jt.jobs.c.account_id == account_id, jt.jobs.c.status.in_(ACTIVE)).limit(1)).first()
    if active is not None:
        raise AuthError(409, "guest_job_active")


def before():
    auth, guest, jobs, store = services()
    receipt = guest.start("guest-acceptance-network", "guest-acceptance",
        initializer=lambda conn, owner, now: seed_guest_trial(
            conn, owner, guest.settings.trial_credits, now))
    draft = QuoteInput(capability_id="test.image.v1", prompt="guest restart acceptance",
                       width=512, height=512)
    quote = jobs.quote(receipt.bearer, receipt.view.csrf_token, draft)
    job = jobs.submit(receipt.bearer, receipt.view.csrf_token,
        CreateJob(quote_id=quote.id, operation_id=uuid4()))
    runner = JobRunner(jobs, store, worker_id="guest-acceptance-worker")
    claim = runner.claim()
    assert claim is not None and claim.job_id == job.id
    runner.execute(claim, render_test_image)
    result = jobs.get(receipt.bearer, job.id)
    assert result.status == "succeeded" and result.asset_id is not None
    data = read_owned(guest, store, receipt.bearer, result.asset_id)
    assert data.startswith(b"\x89PNG")
    with auth.engine.begin() as conn:
        balance = CreditService(clock=auth.clock).overview(conn, receipt.view.account_id, limit=5).balance
    assert balance.available == guest.settings.trial_credits - 1 and balance.reserved == 0
    state = {
        "bearer": receipt.bearer, "csrf": receipt.view.csrf_token,
        "account_id": str(receipt.view.account_id), "job_id": str(job.id),
        "asset_id": str(result.asset_id),
        "email": f"guest-{receipt.view.account_id.hex}@example.invalid",
    }
    auth.engine.dispose()
    print(json.dumps(state, separators=(",", ":")))
    print("GUEST_BEFORE_OK", file=sys.stderr)


def after():
    state = json.load(sys.stdin)
    auth, guest, jobs, store = services()
    account_id, job_id, asset_id = map(UUID,
        (state["account_id"], state["job_id"], state["asset_id"]))
    view = guest.me(state["bearer"])
    assert view.account_id == account_id and view.trial_used is True
    result = jobs.get(state["bearer"], job_id)
    assert result.status == "succeeded" and result.asset_id == asset_id
    assert read_owned(guest, store, state["bearer"], asset_id).startswith(b"\x89PNG")
    with auth.engine.begin() as conn:
        balance = CreditService(clock=auth.clock).overview(conn, account_id, limit=5).balance
    assert balance.available == guest.settings.trial_credits - 1 and balance.reserved == 0

    claimed = guest.claim(state["bearer"], state["csrf"], RegisterInput(
        email=state["email"], display_name="Guest Acceptance", password=CLAIM_PASSWORD),
        "guest-acceptance-network", "guest-acceptance", guard=no_active)
    assert claimed.view.account.id == account_id and claimed.view.account.email == state["email"]
    try:
        guest.me(state["bearer"])
    except AuthError as exc:
        assert exc.code == "guest_required"
    else:
        raise AssertionError("claimed guest bearer remained valid")

    normal = auth.me(claimed.bearer)
    assert normal.account.id == account_id and normal.account.email_verified is False
    normal_jobs = JobService(auth, JobSettings())
    assert normal_jobs.get(claimed.bearer, job_id).asset_id == asset_id
    assert MediaService(auth, store).get(claimed.bearer, asset_id).id == asset_id
    with auth.engine.begin() as conn:
        final = CreditService(clock=auth.clock).overview(conn, account_id, limit=5).balance
    assert final.available == balance.available and final.reserved == 0
    auth.engine.dispose()
    print("GUEST_AFTER_OK", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"before", "after"}:
        raise SystemExit("usage: guest_acceptance.py before|after")
    before() if sys.argv[1] == "before" else after()
