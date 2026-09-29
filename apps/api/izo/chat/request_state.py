"""Request reads, stop transitions and in-process stop signals."""
from threading import Event
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .provider import ProviderFailure
from .schemas import RequestView

UNKNOWN_PAID_OUTCOME = "provider_outcome_unknown"
KNOWN_PROVIDER_REJECTIONS = frozenset({
    "provider_rejected", "credential_rejected", "provider_balance",
    "model_rejected", "provider_rate_limited",
})


class RequestStateMixin:
    def _mark_paid_submission(self, request_id: UUID) -> None:
        # Commit before POST so process loss cannot make a charged call retryable.
        now = self.now()
        with self.engine.begin() as conn:
            marked = conn.execute(sa.update(t.requests).where(
                t.requests.c.id == request_id,
                t.requests.c.state == "streaming",
                t.requests.c.stop_requested_at.is_(None),
                t.requests.c.deadline_at > now).values(
                error_code=UNKNOWN_PAID_OUTCOME, updated_at=now))
            if marked.rowcount != 1:
                raise ProviderFailure("request_expired")

    def _terminal(self, conn, request_id, state: str,
                  error_code: str | None, now: int,
                  content: str | None = None) -> None:
        conn.execute(sa.update(t.requests).where(t.requests.c.id == request_id).values(
            state=state, error_code=error_code, updated_at=now))
        values = {"state": "complete" if state == "completed" else state,
                  "updated_at": now}
        if content is not None:
            values["content"] = content
        conn.execute(sa.update(t.messages).where(
            t.messages.c.request_id == request_id,
            t.messages.c.role == "assistant").values(**values))
        thread_id = conn.execute(sa.select(t.requests.c.thread_id).where(
            t.requests.c.id == request_id)).scalar_one()
        conn.execute(sa.update(t.threads).where(
            t.threads.c.id == thread_id).values(updated_at=now))

    def _finish(self, request_id, state, error_code, content):
        now = self.now()
        with self.engine.begin() as conn:
            current, stopped_at, deadline, prior_code = conn.execute(sa.select(
                t.requests.c.state, t.requests.c.stop_requested_at,
                t.requests.c.deadline_at, t.requests.c.error_code
            ).where(t.requests.c.id == request_id).with_for_update()).one()
            if current in {"completed", "interrupted", "error", "stopped"}:
                return current
            if stopped_at is not None:
                state, error_code = "stopped", None
            elif state == "completed" and now >= deadline:
                state, error_code = "interrupted", "request_expired"
            if (prior_code == UNKNOWN_PAID_OUTCOME and state != "completed"
                    and error_code not in KNOWN_PROVIDER_REJECTIONS):
                error_code = UNKNOWN_PAID_OUTCOME
            self._terminal(conn, request_id, state, error_code, now, content)
        if state != "completed":
            self._signal_stop(request_id)
        return state

    @staticmethod
    def _request_view(row) -> RequestView:
        return RequestView(
            id=row["id"], thread_id=row["thread_id"], model=row["model"],
            state=row["state"], error_code=row["error_code"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            deadline_at=row["deadline_at"])

    def request(self, raw, request_id: UUID) -> RequestView:
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            row = conn.execute(sa.select(t.requests).where(
                t.requests.c.id == request_id,
                t.requests.c.account_id == account["id"])).mappings().first()
            if not row:
                raise ChatError(404, "request_not_found")
            return self._request_view(row)

    def stop(self, raw, csrf, request_id: UUID) -> RequestView:
        now = self.now()
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.requests).where(
                t.requests.c.id == request_id,
                t.requests.c.account_id == account["id"]
            ).with_for_update()).mappings().first()
            if not row:
                raise ChatError(404, "request_not_found")
            if row["state"] in {
                    "completed", "interrupted", "error", "stopped"}:
                return self._request_view(row)
            if row["state"] == "pending":
                conn.execute(sa.update(t.requests).where(
                    t.requests.c.id == request_id).values(
                    state="stopped", stop_requested_at=now, updated_at=now))
                conn.execute(sa.update(t.messages).where(
                    t.messages.c.request_id == request_id,
                    t.messages.c.role == "assistant").values(
                    state="stopped", updated_at=now))
            else:
                conn.execute(sa.update(t.requests).where(
                    t.requests.c.id == request_id).values(
                    stop_requested_at=now, updated_at=now))
        self._signal_stop(request_id)
        return self.request(raw, request_id)

    def _signal_stop(self, request_id: UUID) -> None:
        with self._stop_lock:
            event = self._stops.get(request_id)
            if event:
                event.set()

    def _register_stop(self, request_id: UUID) -> Event:
        with self._stop_lock:
            event = self._stops.setdefault(request_id, Event())
        with self.engine.begin() as conn:
            requested = conn.execute(sa.select(t.requests.c.stop_requested_at).where(
                t.requests.c.id == request_id)).scalar_one()
        if requested is not None:
            event.set()
        return event

    def _unregister_stop(self, request_id: UUID) -> None:
        with self._stop_lock:
            self._stops.pop(request_id, None)
