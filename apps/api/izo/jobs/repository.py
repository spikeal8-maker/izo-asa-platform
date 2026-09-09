"""Bounded job SQL under an already acquired Accounts lock."""
import json
from uuid import uuid4
import sqlalchemy as sa
from . import tables as t
from .schemas import JobError, JobView


def load(conn, owner, job_id):
    row = conn.execute(sa.select(t.jobs).where(t.jobs.c.id == job_id,
        t.jobs.c.account_id == owner).with_for_update()).mappings().first()
    if row is None:
        raise JobError(404, "not_found")
    return row


def change(conn, job_id, now, **values):
    conn.execute(sa.update(t.jobs).where(t.jobs.c.id == job_id).values(updated_at=now, **values))


def event(conn, job_id, kind, now):
    # Durable, payload-minimal delivery intent in the same transaction. No broker
    # or notification call can turn committed generation into a failed job.
    conn.execute(sa.insert(t.outbox).values(id=uuid4(), job_id=job_id, event_type=kind, created_at=now))


def close_attempt(conn, row, state, now):
    if row["attempt_id"]:
        conn.execute(sa.update(t.attempts).where(t.attempts.c.id == row["attempt_id"],
            t.attempts.c.state.in_(("claimed", "running")))
                     .values(state=state, closed_at=now))


def view(row):
    request = json.loads(row["request_json"])
    return JobView(id=row["id"], status=row["status"], **request,
        reserved_credits=row["reserve_credits"] if row["status"] not in {"succeeded", "failed", "cancelled"} else 0,
        charged_credits=row["charged_credits"], asset_id=row["output_id"] if row["status"] == "succeeded" else None,
        error_code=row["error_code"], cancel_requested=row["cancel_requested"],
        created_at=row["created_at"], updated_at=row["updated_at"], attempt_count=row["fence"])
