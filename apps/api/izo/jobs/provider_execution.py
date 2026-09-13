"""Fal job orchestration; provider-call persistence and recovery live in focused modules."""
from __future__ import annotations

import time

from ..media import codec
from ..providers.fal import (FalAdapter, FalAuthRequired, FalPermanent, FalRejected,
                             FalRequestMissing, FalSubmissionUnknown, FalTransient)
from . import catalog
from .provider_calls import ProviderCallStore, handle_from_row, load_call
from .provider_recovery import recover_fal
from .schemas import JobError


class FalJobExecutor:
    def __init__(self, runner, adapter: FalAdapter, *, sleeper=time.sleep):
        if runner.pool != catalog.FAL_POOL:
            raise ValueError("Fal executor requires the fal job pool")
        self.runner, self.adapter, self.sleeper = runner, adapter, sleeper
        self.calls = ProviderCallStore(runner, adapter)

    def _submission_unknown(self, claim):
        try:
            self.calls.update(claim, state="submission_unknown", error="provider_submission_unknown")
            self.runner.reconcile_before_output(claim, "provider_submission_unknown")
        except JobError:
            pass

    def _reconcile(self, claim, code, *, retryable=False):
        try:
            self.calls.update(claim, error=code)
            self.runner.reconcile_before_output(claim, code, retryable=retryable)
        except JobError:
            pass

    def _fail(self, claim, code):
        try:
            self.calls.update(claim, state="failed", error=code)
            self.runner.fail_before_output(claim, code)
        except JobError:
            pass

    def _cancelled(self, claim):
        try:
            self.calls.update(claim, state="cancelled")
            self.runner.cancel_before_output(claim)
        except JobError:
            pass

    def _submit_or_resume(self, claim, draft, call):
        if call["provider_request_id"]:
            return call
        snapshot = self.calls.job_snapshot(claim)
        if snapshot["cancel_requested"]:
            self._cancelled(claim)
            return None
        if call["state"] == "submission_unknown":
            self._reconcile(claim, "provider_submission_unknown")
            return None
        try:
            handle = self.adapter.submit(draft)
        except FalRejected as exc:
            self._fail(claim, exc.code)
            return None
        except FalSubmissionUnknown:
            self._submission_unknown(claim)
            return None
        try:
            still_current = self.calls.save_handle(claim, call["id"], handle)
        except JobError:
            self._reconcile(claim, "provider_submission_unknown")
            return None
        if not still_current:
            return None
        updated = dict(call)
        updated.update(provider_request_id=handle.request_id, status_url=handle.status_url,
                       response_url=handle.response_url, cancel_url=handle.cancel_url,
                       state="accepted")
        return updated

    def _request_cancel(self, claim, handle, call, *, deadline=False):
        try:
            outcome = self.adapter.cancel(handle)
        except FalAuthRequired as exc:
            self._reconcile(claim, exc.code)
            return False
        except (FalTransient, FalPermanent) as exc:
            code = "provider_deadline" if deadline else getattr(exc, "code", "provider_cancel_uncertain")
            self._reconcile(claim, code, retryable=True)
            return False
        if outcome == "missing":
            self._reconcile(claim, "provider_cancel_uncertain", retryable=True)
            return False
        self.calls.update(claim, state="cancel_requested")
        call["state"] = "cancel_requested"
        return True

    def _finish_output(self, claim, draft, handle):
        self.calls.update(claim, state="completed")
        try:
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

    def execute(self, claim, *, stopping=None):
        with self.runner.auth.engine.begin() as conn:
            existing = load_call(conn, claim.job_id)
        allow_expired = bool(existing and existing["provider_request_id"])
        try:
            draft = self.runner.start(claim, allow_expired=allow_expired, allow_restricted=allow_expired)
        except JobError:
            return
        if draft is None:
            return
        try:
            call = self.calls.begin(claim, draft)
        except (JobError, FalRejected):
            self._fail(claim, "provider_budget_exceeded")
            return
        call = self._submit_or_resume(claim, draft, call)
        if call is None:
            return
        if (call["connection_id"] != self.adapter.connection_id
                or call["credential_ref"] != self.adapter.credential_ref):
            self._reconcile(claim, "provider_auth_required")
            return
        handle = handle_from_row(call)

        while True:
            if stopping is not None and stopping.is_set():
                return
            snapshot = self.calls.job_snapshot(claim)
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
            running = status.state in {"IN_QUEUE", "IN_PROGRESS"}
            if snapshot["cancel_requested"] and running and call.get("state") != "cancel_requested":
                if not self._request_cancel(claim, handle, call):
                    return
            if running:
                if snapshot["deadline_at"] <= self.runner.auth.now():
                    if call.get("state") != "cancel_requested" and not self._request_cancel(
                            claim, handle, call, deadline=True):
                        return
                    self._reconcile(claim, "provider_deadline", retryable=True)
                    return
                if call.get("state") != "cancel_requested":
                    self.calls.update(claim, state="running")
                    call["state"] = "running"
                try:
                    self.runner.heartbeat(claim)
                except JobError:
                    self._reconcile(claim, "provider_deadline", retryable=True)
                    return
                self.sleeper(self.adapter.settings.poll_seconds)
                continue
            self._finish_output(claim, draft, handle)
            return


__all__ = ["FalJobExecutor", "recover_fal"]
