"""Crash recovery and bounded reconciliation; an uncertain write is never resubmitted."""
import sqlalchemy as sa
from ..accounts.jobs_access import lock_worker_owner
from ..media import outputs
from . import catalog, tables as t, repository as repo
from .schemas import JobError, QuoteInput


def recover(runner, limit=20):
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid recovery batch")
    auth, now = runner.auth, runner.auth.now()
    with auth.engine.connect() as conn:
        candidates = conn.execute(sa.select(t.jobs.c.id, t.jobs.c.account_id).where(
            t.jobs.c.pool == catalog.POOL, sa.or_(
                sa.and_(t.jobs.c.status == "queued", t.jobs.c.deadline_at <= now),
                sa.and_(t.jobs.c.status.in_(("claimed", "running", "uploading")), t.jobs.c.lease_until <= now)))
            .order_by(t.jobs.c.updated_at, t.jobs.c.id).limit(limit)).all()
    changed = 0
    for job_id, owner in candidates:
        with auth.engine.begin() as conn:
            owner_state = lock_worker_owner(conn, owner, skip_locked=True)
            if owner_state is None:
                continue
            row = repo.load(conn, owner, job_id)
            if row["status"] not in {"queued", "claimed", "running", "uploading"}:
                continue
            if row["status"] != "queued" and row["lease_until"] > auth.now():
                continue
            if row["status"] == "uploading":
                repo.change(conn, job_id, now, status="reconciling", next_poll_at=now,
                            error_code="storage_uncertain", lease_until=0)
            elif (owner_state != "active" or row["deadline_at"] <= now
                  or row["fence"] >= runner.service.policy.max_attempts):
                runner.service.release_terminal(conn, row, "failed", "executor_deadline")
            elif row["status"] != "queued":
                # This release only accepts the local, pure test-image adapter.
                # Never reuse this retry path for a network/paid provider.
                draft = QuoteInput.model_validate_json(row["request_json"])
                if draft.capability_id != catalog.CAPABILITY:
                    raise JobError(409, "reconciliation_required")
                repo.close_attempt(conn, row, "expired", now)
                repo.change(conn, job_id, now, status="queued", attempt_id=None, lease_until=None)
            else:
                continue
            changed += 1
    return changed


def reconcile_one(runner):
    auth, now = runner.auth, runner.auth.now()
    with auth.engine.connect() as conn:
        candidates = conn.execute(sa.select(t.jobs.c.id, t.jobs.c.account_id).where(
            t.jobs.c.pool == catalog.POOL, t.jobs.c.status == "reconciling",
            t.jobs.c.reconcile_count < 5, t.jobs.c.next_poll_at <= now,
            sa.or_(t.jobs.c.lease_until.is_(None), t.jobs.c.lease_until <= now))
            .order_by(t.jobs.c.next_poll_at, t.jobs.c.id).limit(64)).all()
    for job_id, owner in candidates:
        with auth.engine.begin() as conn:
            if lock_worker_owner(conn, owner, skip_locked=True) is None:
                continue
            row = repo.load(conn, owner, job_id)
            if (row["status"] != "reconciling" or row["reconcile_count"] >= 5
                    or row["next_poll_at"] > now or (row["lease_until"] or 0) > now):
                continue
            claim = runner._lease(conn, row, now, "running")
            saved = dict(outputs.load(conn, owner, row["output_id"]))
        try:
            data = runner.store.read(saved["object_key"], saved["byte_size"])
            runner.finish(claim, data)
        except Exception:
            with auth.engine.begin() as conn:
                try:
                    current = runner._locked(conn, claim, lease=False)
                except JobError:
                    return True
                if current["status"] == "reconciling":
                    count = current["reconcile_count"] + 1
                    repo.close_attempt(conn, current, "failed", auth.now())
                    repo.change(conn, job_id, auth.now(), reconcile_count=count, lease_until=0,
                        next_poll_at=auth.now() + min(300, 10 * 2 ** count),
                        error_code="reconciliation_required" if count >= 5 else "storage_uncertain")
                    if count == 5:
                        repo.event(conn, job_id, "reconciliation_required", auth.now())
        return True
    return False
