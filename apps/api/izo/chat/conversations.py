"""Durable Thread/Message/Request ownership, attachments and idempotency."""
import hashlib
import json
from threading import Event
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .credentials import ChatError
from .schemas import AttachmentView, MessageView, RequestView, ThreadDetail, ThreadList, ThreadView
from .schemas import (
    MAX_CHAT_IMAGE_BYTES, MESSAGE_PAGE_LIMIT, MODEL_REVISION,
    REQUEST_WINDOW_LIMIT, THREAD_PAGE_LIMIT,
)


def _sha(value: dict) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ConversationMixin:
    def create_thread(self, raw, csrf, title: str | None) -> ThreadView:
        now, thread_id = self.now(), uuid4()
        safe = (title or "Новый чат").strip()[:120] or "Новый чат"
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            conn.execute(sa.insert(t.threads).values(
                id=thread_id, account_id=account["id"], title=safe,
                next_sequence=1, created_at=now, updated_at=now))
        return ThreadView(
            id=thread_id, title=safe, created_at=now, updated_at=now)

    @staticmethod
    def _thread_view(row) -> ThreadView:
        return ThreadView(
            id=row["id"], title=row["title"],
            created_at=row["created_at"], updated_at=row["updated_at"])

    def list_threads(self, raw) -> ThreadList:
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            rows = conn.execute(sa.select(t.threads).where(
                t.threads.c.account_id == account["id"]).order_by(
                t.threads.c.updated_at.desc(), t.threads.c.id.desc()).limit(
                THREAD_PAGE_LIMIT)).mappings().all()
        return ThreadList(threads=[self._thread_view(row) for row in rows])

    @staticmethod
    def _attachment_view(row) -> AttachmentView:
        return AttachmentView(
            id=row["id"], asset_id=row["asset_id"],
            media_type=row["media_type"], byte_size=row["byte_size"],
            width=row["width"], height=row["height"], sha256=row["sha256"],
            created_at=row["created_at"])

    @classmethod
    def _message_view(cls, row, attachment_rows=()) -> MessageView:
        return MessageView(
            id=row["id"], request_id=row["request_id"], role=row["role"],
            sequence=row["sequence"], content=row["content"], state=row["state"],
            attachments=[cls._attachment_view(item) for item in attachment_rows],
            created_at=row["created_at"], updated_at=row["updated_at"])

    def thread_detail(self, raw, thread_id: UUID) -> ThreadDetail:
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            thread = conn.execute(sa.select(t.threads).where(
                t.threads.c.id == thread_id,
                t.threads.c.account_id == account["id"])).mappings().first()
            if not thread:
                raise ChatError(404, "thread_not_found")
            rows = conn.execute(sa.select(t.messages).where(
                t.messages.c.thread_id == thread_id).order_by(
                t.messages.c.sequence.desc()).limit(
                MESSAGE_PAGE_LIMIT)).mappings().all()
            ordered = list(reversed(rows))
            ids = [row["id"] for row in ordered]
            attachment_rows = conn.execute(sa.select(t.attachments).where(
                t.attachments.c.account_id == account["id"],
                t.attachments.c.message_id.in_(ids)).order_by(
                t.attachments.c.message_id, t.attachments.c.ordinal)
            ).mappings().all() if ids else []
        grouped: dict[UUID, list] = {}
        for item in attachment_rows:
            grouped.setdefault(item["message_id"], []).append(item)
        return ThreadDetail(
            thread=self._thread_view(thread),
            messages=[
                self._message_view(row, grouped.get(row["id"], ()))
                for row in ordered
            ])

    @staticmethod
    def _request_view(row) -> RequestView:
        return RequestView(
            id=row["id"], thread_id=row["thread_id"], model=row["model"],
            state=row["state"], error_code=row["error_code"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            deadline_at=row["deadline_at"])

    @staticmethod
    def _request_fingerprint(
            thread_id, text, model, attachment_ids,
            connection_id, generation) -> str:
        return _sha({
            "thread": str(thread_id), "text": text, "model": model,
            "attachments": [str(item) for item in attachment_ids],
            "model_revision": MODEL_REVISION,
            "connection": str(connection_id),
            "credential_generation": generation,
        })

    def _attachment_assets(self, conn, account_id, command):
        if not command.attachment_ids:
            return []
        if not self.policy.model_supports_vision(command.model):
            raise ChatError(422, "model_vision_unsupported")
        rows = conn.execute(sa.select(t.media_assets).where(
            t.media_assets.c.account_id == account_id,
            t.media_assets.c.id.in_(command.attachment_ids))).mappings().all()
        by_id = {row["id"]: row for row in rows}
        if len(by_id) != len(command.attachment_ids):
            raise ChatError(404, "attachment_not_found")
        ordered = [by_id[item] for item in command.attachment_ids]
        if any(row["byte_size"] > MAX_CHAT_IMAGE_BYTES for row in ordered):
            raise ChatError(413, "image_too_large")
        return ordered

    def create_request(self, raw, csrf, thread_id: UUID, command) -> RequestView:
        now = self.now()
        if not self.policy.model_allowed(command.model):
            raise ChatError(422, "model_not_allowed")
        try:
            with self.engine.begin() as conn:
                account, _ = self._account(conn, raw, csrf, mutation=True)
                existing = conn.execute(sa.select(t.requests).where(
                    t.requests.c.id == command.request_id)).mappings().first()
                if existing:
                    if (existing["account_id"] != account["id"]
                            or existing["thread_id"] != thread_id):
                        raise ChatError(404, "request_not_found")
                    expected = self._request_fingerprint(
                        thread_id, command.text, command.model,
                        command.attachment_ids, existing["connection_id"],
                        existing["credential_generation"])
                    if expected != existing["fingerprint"]:
                        raise ChatError(409, "request_conflict")
                    return self._request_view(existing)

                self._consume_rate(
                    conn, account["id"], "request", REQUEST_WINDOW_LIMIT)
                thread = conn.execute(sa.select(t.threads).where(
                    t.threads.c.id == thread_id,
                    t.threads.c.account_id == account["id"]
                ).with_for_update()).mappings().first()
                if not thread:
                    raise ChatError(404, "thread_not_found")
                connection = conn.execute(sa.select(t.connections).where(
                    t.connections.c.account_id == account["id"]
                ).with_for_update()).mappings().first()
                if (not connection or not connection["enabled"]
                        or connection["verified_at"] is None):
                    raise ChatError(409, "credential_not_verified")

                assets = self._attachment_assets(conn, account["id"], command)
                fingerprint = self._request_fingerprint(
                    thread_id, command.text, command.model,
                    command.attachment_ids, connection["id"],
                    connection["generation"])
                request_id = command.request_id
                sequence = thread["next_sequence"]
                user_message_id, assistant_message_id = uuid4(), uuid4()

                conn.execute(sa.insert(t.requests).values(
                    id=request_id, thread_id=thread_id,
                    account_id=account["id"], fingerprint=fingerprint,
                    model=command.model, model_revision=MODEL_REVISION,
                    connection_id=connection["id"],
                    credential_generation=connection["generation"],
                    state="pending", error_code=None, stop_requested_at=None,
                    created_at=now, updated_at=now,
                    deadline_at=now + self.policy.request_deadline_seconds))
                conn.execute(sa.insert(t.messages), [
                    dict(
                        id=user_message_id, thread_id=thread_id,
                        request_id=request_id, role="user",
                        sequence=sequence, part_version=1,
                        content=command.text, state="complete",
                        created_at=now, updated_at=now),
                    dict(
                        id=assistant_message_id, thread_id=thread_id,
                        request_id=request_id, role="assistant",
                        sequence=sequence + 1, part_version=1,
                        content="", state="partial",
                        created_at=now, updated_at=now),
                ])
                if assets:
                    conn.execute(sa.insert(t.attachments), [
                        dict(
                            id=uuid4(), message_id=user_message_id,
                            request_id=request_id, account_id=account["id"],
                            asset_id=asset["id"], ordinal=index,
                            media_type="image/png", byte_size=asset["byte_size"],
                            width=asset["width"], height=asset["height"],
                            sha256=asset["sha256"], created_at=now,
                        )
                        for index, asset in enumerate(assets)
                    ])

                title = thread["title"]
                if sequence == 1 and title == "Новый чат":
                    title = command.text.replace("\n", " ").strip()[:72] or title
                conn.execute(sa.update(t.threads).where(
                    t.threads.c.id == thread_id).values(
                    next_sequence=sequence + 2,
                    title=title, updated_at=now))
                row = conn.execute(sa.select(t.requests).where(
                    t.requests.c.id == request_id)).mappings().one()
                return self._request_view(row)
        except IntegrityError as exc:
            raise ChatError(409, "active_request_exists") from exc

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
