"""Durable fal provider lifecycle. A lost submit response is never resubmitted automatically."""
from __future__ import annotations

import time
from uuid import uuid4
import sqlalchemy as sa

from ..accounts.jobs_access import lock_worker_owner
from ..media import codec
from ..providers.fal import (FalAdapter, FalAuthRequired, FalHandle, FalPermanent,
                             FalRejected, FalRequestMissing, FalSubmissionUnknown,
                             FalTransient, PROVIDER)
from . import catalog, repository as repo, tables as t
from .schemas import JobError, QuoteInput


def _call(conn, job_id, *, lock=False):
    query = sa.select(t.provider_calls).where(t.provider_calls.c.job_id == job_id)
    if lock:
        query = query.with_for_update()
    return conn.execute(query).mappings().first()


def _handle(row) -> FalHandle:
    return FalHandle(request_id=row["provider_request_id"], status_url=row["status_url"],
                     response_url=row["response_url"], cancel_url=row["cancel_url"])


class FalJobExecutor:
    def __init__(self, runner, adapter: FalAdapter, *, sleeper=time.sleep):
        if runner.pool != catalog.FAL_POOL:
            raise ValueError("Fal executor requires the fal job pool")
        self.runner, self.adapter, self.sleeper = runner, adapter, sleeper

    def _begin_call(self, claim, draft):
        with self.runner.auth.engine.begin() as conn:
            row = self.runner._locked(conn, claim)
            if row["status"] != "running":
                raise JobError(409, "invalid_transition")
            current = _call(conn, row["id"], lock=True)
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

    def _job_snapshot(self, claim):
        with self.runner.auth.engine.begin() as conn:
            row = self.runner._locked(conn, claim, lease=False)
            return dict(row)

    def _save_handle(self, claim, call_id, handle: FalHandle):
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
                    # Recovery expired this attempt while submit was in flight. The late
                    # response supplies the missing durable ID, so resume that same request.
                    repo.change(conn, row["id"], now, status="queued", attempt_id=None,
                                lease_until=None, error_code=None, next_poll_at=now)
                    return False
            return (row["attempt_id"] == claim.attempt_id and row["fence"] == claim.fence
                    and row["status"] in {"claimed", "running"})

    def _update_call(self, claim, *, state=None, error=None):
        with self.runner.auth.engine.begin() as conn:
            row = self.runner._locked(conn, claim, lease=False)
            call = _call(conn, row["id"], lock=True)
            if call is None:
                return
            values = {"updated_at": self.runner.auth.now()}
            if state is not None:
                values["state"] = state
            if error is not None:
                values["last_error_code"] = error
            conn.execute(sa.update(t.provider_calls).where(t.provider_calls.c.id == call["id"]).values(**values))

    def _submission_unknown(self, claim):
        try:
            self._update_call(claim, state="submission_unknown", error="provider_submission_unknown")
            self.runner.reconcile_before_output(claim, "provider_submission_unknown")
        except JobError:
            pass

    def _reconcile(self, claim, code, *, retryable=False):
        try:
            self._update_call(claim, error=code)
            self.runner.reconcile_before_output(claim, code, retryable=retryable)
        except JobError:
            pass

    def _fail(self, claim, code):
        try:
            self._update_call(claim, state="failed", error=code)
            self.runner.fail_before_output(claim, code)
        except JobError:
            pass

    def _cancelled(self, claim):
        try:
            self._update_call(claim, state="cancelled")
            self.runner.cancel_before_output(claim)
        except JobError:
            pass

    def execute(self, claim, *, stopping=None):
        # Existing accepted provider work may be resumed past the local execution deadline;
        # no new provider submission is allowed in that case.
        with self.runner.auth.engine.begin() as conn:
            existing = _call(conn, claim.job_id)
        allow_expired = bool(existing and existing["provider_request_id"])
        try:
            draft = self.runner.start(claim, allow_expired=allow_expired, allow_restricted=allow_expired)
        except JobError:
            return
        if draft is None:
            return
        try:
            call = self._begin_call(claim, draft)
        except (JobError, FalRejected):
            self._fail(claim, "provider_budget_exceeded")
            return

        if not call["provider_request_id"]:
            snapshot = self._job_snapshot(claim)
            if snapshot["cancel_requested"]:
                self._cancelled(claim)
                return
            if call["state"] == "submission_unknown":
                self._reconcile(claim, "provider_submission_unknown")
                return
            try:
                handle = self.adapter.submit(draft)
            except FalRejected as exc:
                self._fail(claim, exc.code)
                return
            except FalSubmissionUnknown:
                self._submission_unknown(claim)
                return
            try:
                still_current = self._save_handle(claim, call["id"], handle)
            except JobError:
                # A conflicting durable call means automatic continuation is unsafe.
                self._reconcile(claim, "provider_submission_unknown")
                return
            if not still_current:
                # The returned request ID is durable; the newer lease will resume it.
                return
            call = dict(call)
            call.update(provider_request_id=handle.request_id, status_url=handle.status_url,
                        response_url=handle.response_url, cancel_url=handle.cancel_url, state="accepted")
        if (call["connection_id"] != self.adapter.connection_id
                or call["credential_ref"] != self.adapter.credential_ref):
            self._reconcile(claim, "provider_auth_required")
            return
        handle = _handle(call)

        while True:
            if stopping is not None and stopping.is_set():
                return
            snapshot = self._job_snapshot(claim)
            try:
                status = self.adapter.status(handle)
            except FalRequestMissing as exc:
                if call.get("state") == "cancel_requested":
                    self._cancelled(claim)
                else:
                    self._reconcile(claim, exc.code)
                return
            except FalAuthRequired as exc:
                self._reconcile(claim, exc.code)
                return
            except FalTransient:
                if snapshot["deadline_at"] <= self.runner.auth.now():
                    self._reconcile(claim, "provider_deadline", retryable=True)
                    return
                try:
                    self.runner.heartbeat(claim)
                except JobError:
                    self._reconcile(claim, "provider_deadline", retryable=True)
                    return
                self.sleeper(self.adapter.settings.poll_seconds)
                continue
            except FalPermanent as exc:
                self._reconcile(claim, exc.code)
                return

            if status.has_error:
                self._fail(claim, "provider_failed")
                return

            if (snapshot["cancel_requested"] and status.state in {"IN_QUEUE", "IN_PROGRESS"}
                    and call.get("state") != "cancel_requested"):
                try:
                    outcome = self.adapter.cancel(handle)
                except FalAuthRequired as exc:
                    self._reconcile(claim, exc.code)
                    return
                except (FalTransient, FalPermanent) as exc:
                    self._reconcile(claim, getattr(exc, "code", "provider_cancel_uncertain"), retryable=True)
                    return
                if outcome == "missing":
                    self._reconcile(claim, "provider_cancel_uncertain", retryable=True)
                    return
                # 202 only means cancellation was requested. The request may have raced
                # into IN_PROGRESS; refund only after a later missing/terminal outcome.
                self._update_call(claim, state="cancel_requested")
                call["state"] = "cancel_requested"

            if status.state in {"IN_QUEUE", "IN_PROGRESS"}:
                if snapshot["deadline_at"] <= self.runner.auth.now():
                    # A deadline requests cancellation, but 202 is not proof that paid work stopped.
                    if call.get("state") != "cancel_requested":
                        try:
                            outcome = self.adapter.cancel(handle)
                        except FalAuthRequired as exc:
                            self._reconcile(claim, exc.code)
                            return
                        except (FalTransient, FalPermanent):
                            self._reconcile(claim, "provider_deadline", retryable=True)
                            return
                        if outcome == "missing":
                            self._reconcile(claim, "provider_cancel_uncertain", retryable=True)
                            return
                        self._update_call(claim, state="cancel_requested")
                        call["state"] = "cancel_requested"
                    self._reconcile(claim, "provider_deadline", retryable=True)
                    return
                if call.get("state") != "cancel_requested":
                    self._update_call(claim, state="running")
                    call["state"] = "running"
                try:
                    self.runner.heartbeat(claim)
                except JobError:
                    self._reconcile(claim, "provider_deadline", retryable=True)
                    return
                self.sleeper(self.adapter.settings.poll_seconds)
                continue

            self._update_call(claim, state="completed")
            try:
                # Provider work is already terminal; extend only this reconciliation lease.
                self.runner.heartbeat(claim, allow_expired=True)
                result = self.adapter.result(handle, width=draft.width, height=draft.height,
                    maximum=catalog.output_bound(draft.width, draft.height))
                image = codec.decode(result.data, result.content_type, draft.width, draft.height,
                                     catalog.output_bound(draft.width, draft.height))
                key = self.runner.seal(claim, image, allow_restricted=True)
                if key is None:
                    return
            except FalAuthRequired as exc:
                self._reconcile(claim, exc.code)
                return
            except FalTransient:
                self._reconcile(claim, "provider_output_uncertain", retryable=True)
                return
            except JobError:
                # Provider completion is already known. A local lease/state race must
                # keep the reservation and resume the same provider request.
                self._reconcile(claim, "provider_output_uncertain", retryable=True)
                return
            except FalPermanent as exc:
                self._fail(claim, exc.code)
                return
            except Exception:
                self._fail(claim, "provider_invalid_result")
                return
            try:
                self.runner.store.put(key, image.data, "image/png")
                self.runner.finish(claim, image.data)
            except Exception:
                try:
                    self.runner.uncertain(claim)
                except JobError:
                    pass
            return


def recover_fal(runner, limit=20):
    """Recover known fal requests without ever issuing a second provider submit."""
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
            call = _call(conn, job_id, lock=True)
            if row["status"] == "uploading" and (row["lease_until"] or 0) <= now:
                repo.change(conn, job_id, now, status="reconciling", error_code="storage_uncertain",
                            lease_until=0, next_poll_at=now)
                changed += 1
                continue
            if row["status"] == "reconciling":
                if row["error_code"] not in retryable or row["reconcile_count"] >= 5 \
                        or row["next_poll_at"] > now:
                    continue
                # Only a persisted provider request ID is safe to resume. A lost submit
                # response without an ID remains an operator reconciliation case.
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
                # No durable network intent exists, so this is safe to re-lease.
                repo.close_attempt(conn, row, "expired", now)
                repo.change(conn, job_id, now, status="queued", attempt_id=None, lease_until=None)
            elif call["provider_request_id"]:
                # Resume exactly the same provider request under a new fencing token.
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
