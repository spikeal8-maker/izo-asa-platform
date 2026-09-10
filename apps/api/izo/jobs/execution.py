"""Leased test execution. Every mutation uses Account -> Job -> Media/Credits."""
import re
from uuid import uuid4, uuid5
import sqlalchemy as sa

from ..accounts.jobs_access import lock_worker_owner
from ..credits.service import CreditService
from ..credits.schemas import Settle
from ..media import outputs, codec
from . import catalog, repository as repo, tables as t
from .schemas import Claim, JobError, QuoteInput, TERMINAL


class JobRunner:
    def __init__(self, service, store, worker_id="test-worker", pool=catalog.POOL):
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,80}", worker_id):
            raise ValueError("Invalid worker ID")
        self.service, self.auth, self.store, self.worker_id, self.pool = service, service.auth, store, worker_id, pool

    def _locked(self, conn, claim, *, lease=True):
        lock_worker_owner(conn, claim.account_id)
        row = repo.load(conn, claim.account_id, claim.job_id)
        if row["attempt_id"] != claim.attempt_id or row["fence"] != claim.fence:
            raise JobError(409, "stale_attempt")
        if lease and (row["lease_until"] is None or row["lease_until"] <= self.auth.now()):
            raise JobError(409, "lease_expired")
        return row

    def _lease(self, conn, row, now, state="claimed"):
        attempt_id, fence = uuid4(), row["fence"] + 1
        repo.close_attempt(conn, row, "expired", now)
        conn.execute(sa.insert(t.attempts).values(id=attempt_id, job_id=row["id"],
            fence=fence, worker_id=self.worker_id, state=state, created_at=now))
        repo.change(conn, row["id"], now, attempt_id=attempt_id, fence=fence,
                    lease_until=now + self.service.policy.lease_seconds)
        return Claim(row["id"], row["account_id"], attempt_id, fence)

    def claim(self):
        self.service.require_pool_enabled(self.pool)
        with self.auth.engine.connect() as conn:
            candidates = conn.execute(sa.select(t.jobs.c.id, t.jobs.c.account_id).where(
                t.jobs.c.status == "queued", t.jobs.c.pool == self.pool)
                .order_by(t.jobs.c.created_at, t.jobs.c.id).limit(64)).all()
        for job_id, owner in candidates:
            with self.auth.engine.begin() as conn:
                state = lock_worker_owner(conn, owner, skip_locked=True)
                if state is None:
                    continue
                row = repo.load(conn, owner, job_id)
                if row["status"] != "queued":
                    continue
                now = self.auth.now()
                if state != "active" or row["deadline_at"] <= now:
                    self.service.release_terminal(conn, row, "failed", "admission_expired")
                    continue
                claim = self._lease(conn, row, now)
                repo.change(conn, job_id, now, status="claimed")
                return claim
        return None

    def start(self, claim):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim)
            if row["status"] != "claimed":
                raise JobError(409, "invalid_transition")
            state = lock_worker_owner(conn, claim.account_id)
            if state != "active" or row["deadline_at"] <= self.auth.now():
                self.service.release_terminal(conn, row, "failed", "admission_expired")
                return None
            repo.change(conn, row["id"], self.auth.now(), status="running")
            conn.execute(sa.update(t.attempts).where(t.attempts.c.id == claim.attempt_id).values(state="running"))
            return QuoteInput.model_validate_json(row["request_json"])

    def execution_snapshot(self, claim):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim)
            if not row["execution_json"]:
                return None
            return row["execution_json"]

    def heartbeat(self, claim):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim)
            if row["status"] not in {"claimed", "running", "uploading"}:
                raise JobError(409, "invalid_transition")
            now = self.auth.now()
            if row["deadline_at"] <= now:
                raise JobError(409, "executor_deadline")
            repo.change(conn, row["id"], now,
                        lease_until=min(row["deadline_at"], now + self.service.policy.lease_seconds))

    def seal(self, claim, image):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim)
            if row["status"] != "running":
                raise JobError(409, "invalid_transition")
            if lock_worker_owner(conn, claim.account_id) != "active":
                self.service.release_terminal(conn, row, "cancelled", "account_restricted")
                return None
            key = outputs.seal(conn, claim.account_id, row["output_id"], image.data)
            repo.change(conn, row["id"], self.auth.now(), status="uploading")
            return key

    def record_provider_result(self, claim, *, provider_ref=None, provider_cost_usd=None):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim)
            if row["status"] != "running":
                raise JobError(409, "invalid_transition")
            values = {}
            if provider_ref is not None:
                values["provider_ref"] = provider_ref
            if provider_cost_usd is not None:
                values["provider_cost_usd"] = provider_cost_usd
            if values:
                repo.change(conn, row["id"], self.auth.now(), **values)

    def finish(self, claim, data, *, provider_ref=None, provider_cost_usd=None):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim, lease=False)
            if row["status"] == "succeeded":
                return repo.view(row)
            if row["status"] not in {"uploading", "reconciling"}:
                raise JobError(409, "invalid_transition")
            if row["lease_until"] <= self.auth.now():
                raise JobError(409, "lease_expired")
            now = self.auth.now()
            outputs.finalize(conn, claim.account_id, row["output_id"], data, now)
            CreditService(clock=lambda: now).settle(conn, claim.account_id, Settle(
                operation_id=uuid5(row["id"], "settle"), reservation_id=row["reservation_id"],
                amount=row["reserve_credits"]))
            repo.close_attempt(conn, row, "succeeded", now)
            values = dict(status="succeeded", charged_credits=row["reserve_credits"],
                          error_code=None, lease_until=None)
            if provider_ref is not None:
                values["provider_ref"] = provider_ref
            if provider_cost_usd is not None:
                values["provider_cost_usd"] = provider_cost_usd
            repo.change(conn, row["id"], now, **values)
            repo.event(conn, row["id"], "succeeded", now)
            return repo.view(repo.load(conn, claim.account_id, claim.job_id))

    def uncertain(self, claim):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim, lease=False)
            if row["status"] not in {"uploading", "reconciling"}:
                return
            repo.change(conn, row["id"], self.auth.now(), status="reconciling", lease_until=0,
                        error_code="storage_uncertain", next_poll_at=self.auth.now())

    def provider_uncertain(self, claim, code="provider_outcome_unknown"):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim, lease=False)
            if row["status"] not in {"claimed", "running"}:
                raise JobError(409, "invalid_transition")
            now = self.auth.now()
            repo.close_attempt(conn, row, "failed", now)
            repo.change(conn, row["id"], now, status="reconciling", lease_until=0,
                        next_poll_at=now, error_code=code)
            repo.event(conn, row["id"], "provider_reconciliation_required", now)

    def fail_before_output(self, claim):
        with self.auth.engine.begin() as conn:
            row = self._locked(conn, claim, lease=False)
            if row["status"] in {"claimed", "running"}:
                self.service.release_terminal(conn, row, "failed", "test_executor_failed")

    def execute(self, claim, render):
        try:
            draft = self.start(claim)
            if draft is None:
                return
            data = render(draft)
            image = codec.decode(data, "image/png", draft.width, draft.height,
                                 catalog.output_bound(draft.width, draft.height))
            key = self.seal(claim, image)
            if key is None:
                return
        except Exception:
            try:
                self.fail_before_output(claim)
            except JobError:
                pass  # Cancel/recovery already owns the newer state.
            return
        try:
            self.store.put(key, image.data, "image/png")
            self.finish(claim, image.data)
        except Exception:
            try:
                self.uncertain(claim)
            except JobError:
                pass  # A newer fencing token owns reconciliation.
