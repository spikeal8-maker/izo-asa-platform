"""Recovery of known fal requests without a second provider submission."""
import sqlalchemy as sa

from ..accounts.jobs_access import lock_worker_owner
from . import catalog, repository as repo, tables as t
from .provider_calls import load_call


def recover_fal(runner, limit=20):
    if runner.pool != catalog.FAL_POOL:
        raise ValueError("Fal recovery requires the fal pool")
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid recovery batch")
    auth, now = runner.auth, runner.auth.now()
    retryable = ("provider_output_uncertain", "provider_deadline", "provider_cancel_uncertain")
    with auth.engine.connect() as conn:
        candidates = conn.execute(sa.select(t.jobs.c.id, t.jobs.c.account_id).where(
            t.jobs.c.pool == runner.pool,
            sa.or_(
                sa.and_(t.jobs.c.status.in_(("claimed", "running", "uploading")),
                        t.jobs.c.lease_until <= now),
                sa.and_(t.jobs.c.status == "reconciling",
                        t.jobs.c.error_code.in_(retryable),
                        t.jobs.c.reconcile_count < 5,
                        t.jobs.c.next_poll_at <= now)))
            .order_by(t.jobs.c.updated_at, t.jobs.c.id).limit(limit)).all()
    changed = 0
    for job_id, owner in candidates:
        with auth.engine.begin() as conn:
            if lock_worker_owner(conn, owner, skip_locked=True) is None:
                continue
            row = repo.load(conn, owner, job_id)
            call = load_call(conn, job_id, lock=True)
            if row["status"] == "uploading" and (row["lease_until"] or 0) <= now:
                repo.change(conn, job_id, now, status="reconciling", error_code="storage_uncertain",
                            lease_until=0, next_poll_at=now)
                changed += 1
                continue
            if row["status"] == "reconciling":
                if row["error_code"] not in retryable or row["reconcile_count"] >= 5 \
                        or row["next_poll_at"] > now:
                    continue
                if call is None or not call["provider_request_id"]:
                    continue
                repo.close_attempt(conn, row, "expired", now)
                repo.change(conn, job_id, now, status="queued", attempt_id=None,
                            lease_until=None, error_code=None, next_poll_at=now)
                changed += 1
                continue
            if row["status"] not in {"claimed", "running"} or (row["lease_until"] or 0) > now:
                continue
            if call is None:
                repo.close_attempt(conn, row, "expired", now)
                repo.change(conn, job_id, now, status="queued", attempt_id=None, lease_until=None)
            elif call["provider_request_id"]:
                repo.close_attempt(conn, row, "expired", now)
                repo.change(conn, job_id, now, status="queued", attempt_id=None, lease_until=None)
            else:
                conn.execute(sa.update(t.provider_calls).where(t.provider_calls.c.id == call["id"]).values(
                    state="submission_unknown", last_error_code="provider_submission_unknown", updated_at=now))
                repo.close_attempt(conn, row, "failed", now)
                repo.change(conn, job_id, now, status="reconciling", lease_until=0,
                            error_code="provider_submission_unknown", next_poll_at=now)
                exists = conn.execute(sa.select(t.outbox.c.id).where(
                    t.outbox.c.job_id == job_id,
                    t.outbox.c.event_type == "provider_submission_unknown")).first()
                if exists is None:
                    repo.event(conn, job_id, "provider_submission_unknown", now)
            changed += 1
    return changed
