"""Durable provider-call persistence for fal job execution."""
from uuid import uuid4

import sqlalchemy as sa

from ..accounts.jobs_access import lock_worker_owner
from ..providers.fal import FalHandle, PROVIDER
from . import repository as repo, tables as t
from .schemas import JobError


def load_call(conn, job_id, *, lock=False):
    query = sa.select(t.provider_calls).where(t.provider_calls.c.job_id == job_id)
    if lock:
        query = query.with_for_update()
    return conn.execute(query).mappings().first()


def handle_from_row(row) -> FalHandle:
    return FalHandle(request_id=row["provider_request_id"], status_url=row["status_url"],
                     response_url=row["response_url"], cancel_url=row["cancel_url"])


class ProviderCallStore:
    def __init__(self, runner, adapter):
        self.runner = runner
        self.adapter = adapter

    def begin(self, claim, draft):
        with self.runner.auth.engine.begin() as conn:
            row = self.runner._locked(conn, claim)
            if row["status"] != "running":
                raise JobError(409, "invalid_transition")
            current = load_call(conn, row["id"], lock=True)
            if current is not None:
                return dict(current)
            if lock_worker_owner(conn, claim.account_id) != "active":
                self.runner.service.release_terminal(conn, row, "cancelled", "account_restricted")
                raise JobError(409, "account_restricted")
            now = self.runner.auth.now()
            call_id = uuid4()
            conn.execute(sa.insert(t.provider_calls).values(
                id=call_id, job_id=row["id"], provider=PROVIDER,
                connection_id=self.adapter.connection_id,
                credential_ref=self.adapter.credential_ref,
                provider_request_id=None, status_url=None, response_url=None, cancel_url=None,
                state="submitting", estimated_cost_microusd=self.adapter.estimate(draft.width, draft.height),
                reported_cost_microusd=None, last_error_code=None,
                created_at=now, updated_at=now))
            return dict(conn.execute(sa.select(t.provider_calls).where(
                t.provider_calls.c.id == call_id)).mappings().one())

    def job_snapshot(self, claim):
        with self.runner.auth.engine.begin() as conn:
            row = self.runner._locked(conn, claim, lease=False)
            return dict(row)

    def save_handle(self, claim, call_id, handle: FalHandle):
        """Persist a returned provider ID even if this worker's lease expired in flight."""
        with self.runner.auth.engine.begin() as conn:
            lock_worker_owner(conn, claim.account_id)
            row = repo.load(conn, claim.account_id, claim.job_id)
            call = conn.execute(sa.select(t.provider_calls).where(
                t.provider_calls.c.id == call_id, t.provider_calls.c.job_id == row["id"])
                .with_for_update()).mappings().first()
            if call is None:
                raise JobError(409, "provider_call_conflict")
            existing = call["provider_request_id"]
            if existing is not None and existing != handle.request_id:
                raise JobError(409, "provider_call_conflict")
            if existing is None:
                if call["state"] not in {"submitting", "submission_unknown"}:
                    raise JobError(409, "provider_call_conflict")
                now = self.runner.auth.now()
                conn.execute(sa.update(t.provider_calls).where(t.provider_calls.c.id == call["id"]).values(
                    provider_request_id=handle.request_id, status_url=handle.status_url,
                    response_url=handle.response_url, cancel_url=handle.cancel_url,
                    state="accepted", updated_at=now, last_error_code=None))
                if (row["status"] == "reconciling"
                        and row["error_code"] == "provider_submission_unknown"):
                    repo.change(conn, row["id"], now, status="queued", attempt_id=None,
                                lease_until=None, error_code=None, next_poll_at=now)
                    return False
            return (row["attempt_id"] == claim.attempt_id and row["fence"] == claim.fence
                    and row["status"] in {"claimed", "running"})

    def update(self, claim, *, state=None, error=None):
        with self.runner.auth.engine.begin() as conn:
            row = self.runner._locked(conn, claim, lease=False)
            call = load_call(conn, row["id"], lock=True)
            if call is None:
                return
            values = {"updated_at": self.runner.auth.now()}
            if state is not None:
                values["state"] = state
            if error is not None:
                values["last_error_code"] = error
            conn.execute(sa.update(t.provider_calls).where(t.provider_calls.c.id == call["id"]).values(**values))
