"""Request reads, stop transitions and in-process stop signals."""
from threading import Event
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credentials import ChatError
from .schemas import RequestView


class RequestStateMixin:
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
