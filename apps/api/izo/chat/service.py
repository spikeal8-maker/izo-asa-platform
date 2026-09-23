"""Durable account-owned Chat lifecycle and idempotent request execution."""
from __future__ import annotations

import hashlib
import json
import time
from threading import Event, Lock
from uuid import UUID, uuid4

import sqlalchemy as sa
from cryptography.exceptions import InvalidTag
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .crypto import decrypt, encrypt, operation_fingerprint
from .provider import ProviderFailure
from .schemas import (
    ChatPolicyView, CredentialView, MessageView, ModelView, RequestView,
    ThreadDetail, ThreadList, ThreadView,
)
from .settings import (
    CREDENTIAL_WINDOW_LIMIT, DEFAULT_MODEL, MAX_CONTEXT_CHARS, MAX_CONTEXT_MESSAGES,
    MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS, MESSAGE_PAGE_LIMIT, MODEL_REVISION, MODELS,
    REQUEST_WINDOW_LIMIT, REQUEST_WINDOW_SECONDS, THREAD_PAGE_LIMIT,
)

class ChatError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code
        super().__init__(code)

def _sha(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

class ChatService:
    def __init__(self, auth, policy, provider, clock=time.time):
        self.auth, self.engine, self.policy = auth, auth.engine, policy
        self.provider, self.clock = provider, clock
        self._stops: dict[UUID, Event] = {}
        self._stop_lock = Lock()
        self._recover_stale()

    def now(self) -> int:
        return int(self.clock())

    def _recover_stale(self) -> None:
        now = self.now()
        try:
            with self.engine.begin() as conn:
                stale = list(conn.execute(sa.select(t.requests.c.id).where(
                    t.requests.c.state == "streaming")).scalars())
                if stale:
                    conn.execute(sa.update(t.requests).where(
                        t.requests.c.id.in_(stale)).values(
                        state="interrupted", error_code="executor_restarted", updated_at=now))
                    conn.execute(sa.update(t.messages).where(
                        t.messages.c.request_id.in_(stale),
                        t.messages.c.role == "assistant",
                        t.messages.c.state == "partial").values(
                        state="interrupted", updated_at=now))
        except Exception:
            # Composition/OpenAPI import remains side-effect free; real routes authenticate
            # against the database and fail closed if it is unavailable.
            pass

    def _account(self, conn, raw, csrf=None, mutation=False):
        account, session = self.auth._session(conn, raw, csrf, mutation=mutation)
        if account["state"] != "active":
            raise ChatError(403, "chat_unavailable")
        if not self.policy.admitted(account.get("email")):
            raise ChatError(403, "chat_preview_not_enabled")
        return account, session

    def _consume_rate(self, conn, account_id, kind: str, maximum: int) -> None:
        now = self.now()
        start = now - now % REQUEST_WINDOW_SECONDS
        if conn.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif conn.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError("Unsupported chat database")
        query = insert(t.limits).values(
            account_id=account_id, kind=kind, window_start=start, count=1)
        query = query.on_conflict_do_update(
            index_elements=[t.limits.c.account_id, t.limits.c.kind, t.limits.c.window_start],
            set_={"count": sa.case(
                (t.limits.c.count <= maximum, t.limits.c.count + 1),
                else_=t.limits.c.count)}).returning(t.limits.c.count)
        count = conn.execute(query).scalar_one()
        conn.execute(sa.delete(t.limits).where(
            t.limits.c.window_start < start - 2 * REQUEST_WINDOW_SECONDS))
        if count > maximum:
            raise ChatError(429, "chat_rate_limited")

    def public_policy(self, raw) -> ChatPolicyView:
        with self.engine.begin() as conn:
            self._account(conn, raw)
        return ChatPolicyView(
            revision=MODEL_REVISION,
            default_model=DEFAULT_MODEL,
            models=[ModelView(id=model, label=label) for model, label in MODELS],
            max_input_chars=MAX_INPUT_CHARS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    @staticmethod
    def _credential_view(row) -> CredentialView:
        if not row:
            return CredentialView(configured=False, enabled=False, verified=False)
        return CredentialView(
            configured=True, enabled=row["enabled"],
            verified=row["verified_at"] is not None,
            revision=row["revision"], generation=row["generation"])

    def credential(self, raw) -> CredentialView:
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"])).mappings().first()
            return self._credential_view(row)

    def _root(self) -> bytes:
        try:
            return self.policy.root_key_bytes()
        except RuntimeError:
            raise ChatError(503, "credential_storage_unavailable") from None

    @staticmethod
    def _active_for_connection(conn, connection_id) -> bool:
        return conn.execute(sa.select(t.requests.c.id).where(
            t.requests.c.connection_id == connection_id,
            t.requests.c.state.in_(("pending", "streaming"))).limit(1)).first() is not None

    def save_credential(self, raw, csrf, command) -> CredentialView:
        root = self._root()
        key = command.key.get_secret_value()
        operation_hash = operation_fingerprint(
            root, "save", (str(command.expected_revision) + "\0" + key).encode("utf-8"))
        now = self.now()
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
            if row and row["last_operation_id"] == command.operation_id:
                if row["last_operation_hash"] != operation_hash:
                    raise ChatError(409, "operation_conflict")
                return self._credential_view(row)
            self._consume_rate(conn, account["id"], "credential", CREDENTIAL_WINDOW_LIMIT)
            if row and command.expected_revision != row["revision"]:
                raise ChatError(409, "credential_revision_conflict")
            if not row and command.expected_revision is not None:
                raise ChatError(409, "credential_revision_conflict")
            if row and self._active_for_connection(conn, row["id"]):
                raise ChatError(409, "credential_in_use")
            connection_id = row["id"] if row else uuid4()
            generation = row["generation"] + 1 if row else 1
            revision = row["revision"] + 1 if row else 1
            nonce, ciphertext = encrypt(
                root, account["id"], connection_id, generation, key)
            values = dict(
                provider="deepseek", generation=generation, revision=revision,
                nonce=nonce, ciphertext=ciphertext, enabled=True, verified_at=None,
                last_operation_id=command.operation_id,
                last_operation_hash=operation_hash, updated_at=now)
            if row:
                conn.execute(sa.update(t.connections).where(
                    t.connections.c.id == connection_id).values(**values))
            else:
                conn.execute(sa.insert(t.connections).values(
                    id=connection_id, account_id=account["id"],
                    created_at=now, **values))
            return CredentialView(
                configured=True, enabled=True, verified=False,
                revision=revision, generation=generation)

    def verify_credential(self, raw, csrf, command) -> CredentialView:
        root = self._root()
        op_hash = operation_fingerprint(
            root, "verify", f"{command.expected_revision}".encode("ascii"))
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
            if not row or not row["enabled"]:
                raise ChatError(409, "credential_not_configured")
            if row["last_operation_id"] == command.operation_id:
                if row["last_operation_hash"] != op_hash:
                    raise ChatError(409, "operation_conflict")
                return self._credential_view(row)
            self._consume_rate(conn, account["id"], "credential", CREDENTIAL_WINDOW_LIMIT)
            if row["revision"] != command.expected_revision:
                raise ChatError(409, "credential_revision_conflict")
            snapshot = dict(row)
            try:
                key = decrypt(
                    root, account["id"], row["id"], row["generation"],
                    row["nonce"], row["ciphertext"])
            except (InvalidTag, UnicodeError, ValueError):
                raise ChatError(503, "credential_unavailable") from None
        try:
            self.provider.verify(
                key, timeout=min(15, self.policy.request_deadline_seconds))
        except ProviderFailure as exc:
            status = 422 if exc.code == "credential_rejected" else 503
            raise ChatError(status, exc.code) from None
        now = self.now()
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
            if (not row or row["id"] != snapshot["id"]
                    or row["revision"] != snapshot["revision"]
                    or row["generation"] != snapshot["generation"]):
                raise ChatError(409, "credential_changed")
            revision = row["revision"] + 1
            conn.execute(sa.update(t.connections).where(
                t.connections.c.id == row["id"]).values(
                verified_at=now, revision=revision, updated_at=now,
                last_operation_id=command.operation_id,
                last_operation_hash=op_hash))
            return CredentialView(
                configured=True, enabled=True, verified=True,
                revision=revision, generation=row["generation"])

    def disable_credential(self, raw, csrf, command) -> CredentialView:
        root = self._root()
        op_hash = operation_fingerprint(
            root, "disable", f"{command.expected_revision}".encode("ascii"))
        now = self.now()
        streaming: list[UUID] = []
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
            if not row:
                raise ChatError(409, "credential_not_configured")
            if row["last_operation_id"] == command.operation_id:
                if row["last_operation_hash"] != op_hash:
                    raise ChatError(409, "operation_conflict")
                return self._credential_view(row)
            self._consume_rate(conn, account["id"], "credential", CREDENTIAL_WINDOW_LIMIT)
            if row["revision"] != command.expected_revision:
                raise ChatError(409, "credential_revision_conflict")
            pending = list(conn.execute(sa.select(t.requests.c.id).where(
                t.requests.c.connection_id == row["id"],
                t.requests.c.state == "pending")).scalars())
            streaming = list(conn.execute(sa.select(t.requests.c.id).where(
                t.requests.c.connection_id == row["id"],
                t.requests.c.state == "streaming")).scalars())
            revision = row["revision"] + 1
            conn.execute(sa.update(t.connections).where(
                t.connections.c.id == row["id"]).values(
                enabled=False, verified_at=None, revision=revision, updated_at=now,
                last_operation_id=command.operation_id,
                last_operation_hash=op_hash))
            if pending:
                conn.execute(sa.update(t.requests).where(
                    t.requests.c.id.in_(pending)).values(
                    state="stopped", stop_requested_at=now, updated_at=now))
                conn.execute(sa.update(t.messages).where(
                    t.messages.c.request_id.in_(pending),
                    t.messages.c.role == "assistant").values(
                    state="stopped", updated_at=now))
            if streaming:
                conn.execute(sa.update(t.requests).where(
                    t.requests.c.id.in_(streaming)).values(
                    stop_requested_at=now, updated_at=now))
            generation = row["generation"]
        for request_id in streaming:
            self._signal_stop(request_id)
        return CredentialView(
            configured=True, enabled=False, verified=False,
            revision=revision, generation=generation)

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
    def _message_view(row) -> MessageView:
        return MessageView(
            id=row["id"], request_id=row["request_id"], role=row["role"],
            sequence=row["sequence"], content=row["content"], state=row["state"],
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
        return ThreadDetail(
            thread=self._thread_view(thread),
            messages=[self._message_view(row) for row in reversed(rows)])

    @staticmethod
    def _request_view(row) -> RequestView:
        return RequestView(
            id=row["id"], thread_id=row["thread_id"], model=row["model"],
            state=row["state"], error_code=row["error_code"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            deadline_at=row["deadline_at"])

    @staticmethod
    def _request_fingerprint(
            thread_id, text, model, connection_id, generation) -> str:
        return _sha({
            "thread": str(thread_id), "text": text, "model": model,
            "model_revision": MODEL_REVISION,
            "connection": str(connection_id),
            "credential_generation": generation,
        })

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
                        existing["connection_id"],
                        existing["credential_generation"])
                    if expected != existing["fingerprint"]:
                        raise ChatError(409, "request_conflict")
                    return self._request_view(existing)
                self._consume_rate(
                    conn, account["id"], "request", REQUEST_WINDOW_LIMIT)
                thread = conn.execute(sa.select(t.threads).where(
                    t.threads.c.id == thread_id,
                    t.threads.c.account_id == account["id"]).with_for_update()).mappings().first()
                if not thread:
                    raise ChatError(404, "thread_not_found")
                connection = conn.execute(sa.select(t.connections).where(
                    t.connections.c.account_id == account["id"]).with_for_update()).mappings().first()
                if (not connection or not connection["enabled"]
                        or connection["verified_at"] is None):
                    raise ChatError(409, "credential_not_verified")
                fingerprint = self._request_fingerprint(
                    thread_id, command.text, command.model,
                    connection["id"], connection["generation"])
                request_id = command.request_id
                sequence = thread["next_sequence"]
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
                        id=uuid4(), thread_id=thread_id,
                        request_id=request_id, role="user",
                        sequence=sequence, part_version=1,
                        content=command.text, state="complete",
                        created_at=now, updated_at=now),
                    dict(
                        id=uuid4(), thread_id=thread_id,
                        request_id=request_id, role="assistant",
                        sequence=sequence + 1, part_version=1,
                        content="", state="partial",
                        created_at=now, updated_at=now),
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
                t.requests.c.account_id == account["id"]).with_for_update()).mappings().first()
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
            return event

    def _unregister_stop(self, request_id: UUID) -> None:
        with self._stop_lock:
            self._stops.pop(request_id, None)

    def stream_events(self, raw, request_id: UUID):
        execute = False
        with self.engine.begin() as conn:
            account, _ = self._account(conn, raw)
            row = conn.execute(sa.select(t.requests).where(
                t.requests.c.id == request_id,
                t.requests.c.account_id == account["id"]).with_for_update()).mappings().first()
            if not row:
                raise ChatError(404, "request_not_found")
            now = self.now()
            if row["state"] == "pending":
                if row["deadline_at"] <= now:
                    self._terminal(
                        conn, request_id, "interrupted",
                        "request_expired", now)
                    row = conn.execute(sa.select(t.requests).where(
                        t.requests.c.id == request_id)).mappings().one()
                else:
                    conn.execute(sa.update(t.requests).where(
                        t.requests.c.id == request_id,
                        t.requests.c.state == "pending").values(
                        state="streaming", updated_at=now))
                    execute = True
                    row = dict(row)
                    row["state"] = "streaming"
            account_id = account["id"]
        if execute:
            return self._execute(account_id, dict(row))
        return self._follow(account_id, request_id)

    @staticmethod
    def _event(name: str, payload: dict) -> str:
        return (
            f"event: {name}\n"
            f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
        )

    def _context_and_key(self, account_id, request_row):
        root = self._root()
        with self.engine.begin() as conn:
            connection = conn.execute(sa.select(t.connections).where(
                t.connections.c.id == request_row["connection_id"],
                t.connections.c.account_id == account_id)).mappings().first()
            if (not connection or not connection["enabled"]
                    or connection["generation"]
                    != request_row["credential_generation"]):
                raise ChatError(503, "credential_unavailable")
            try:
                key = decrypt(
                    root, account_id, connection["id"],
                    connection["generation"], connection["nonce"],
                    connection["ciphertext"])
            except (InvalidTag, UnicodeError, ValueError):
                raise ChatError(503, "credential_unavailable") from None
            user = conn.execute(sa.select(t.messages).where(
                t.messages.c.request_id == request_row["id"],
                t.messages.c.role == "user")).mappings().one()
            prior = conn.execute(sa.select(t.messages).where(
                t.messages.c.thread_id == request_row["thread_id"],
                t.messages.c.sequence < user["sequence"],
                t.messages.c.state == "complete").order_by(
                t.messages.c.sequence.desc()).limit(
                MAX_CONTEXT_MESSAGES)).mappings().all()
        chosen, used = [], len(user["content"])
        for item in prior:
            if used + len(item["content"]) > MAX_CONTEXT_CHARS:
                break
            chosen.append({
                "role": item["role"], "content": item["content"]})
            used += len(item["content"])
        chosen.reverse()
        chosen.append({"role": "user", "content": user["content"]})
        return key, chosen

    def _save_partial(self, request_id, content: str) -> None:
        now = self.now()
        with self.engine.begin() as conn:
            state = conn.execute(sa.select(t.requests.c.state).where(
                t.requests.c.id == request_id)).scalar_one_or_none()
            if state != "streaming":
                return
            conn.execute(sa.update(t.messages).where(
                t.messages.c.request_id == request_id,
                t.messages.c.role == "assistant").values(
                content=content, state="partial", updated_at=now))
            conn.execute(sa.update(t.requests).where(
                t.requests.c.id == request_id).values(updated_at=now))

    def _terminal(
            self, conn, request_id, state: str,
            error_code: str | None, now: int,
            content: str | None = None) -> None:
        conn.execute(sa.update(t.requests).where(
            t.requests.c.id == request_id).values(
            state=state, error_code=error_code, updated_at=now))
        message_state = "complete" if state == "completed" else state
        values = {"state": message_state, "updated_at": now}
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
            current = conn.execute(sa.select(t.requests.c.state).where(
                t.requests.c.id == request_id).with_for_update()).scalar_one()
            if current in {
                    "completed", "interrupted", "error", "stopped"}:
                return current
            self._terminal(
                conn, request_id, state, error_code, now, content)
        return state

    def _execute(self, account_id, request_row):
        request_id = request_row["id"]
        event = self._register_stop(request_id)
        content, saved_at, saved_len = "", time.monotonic(), 0
        sequence = 0
        yield self._event(
            "message.start",
            {"request_id": str(request_id), "sequence": sequence})
        try:
            key, messages = self._context_and_key(
                account_id, request_row)
            for chunk in self.provider.stream(
                    key, request_row["model"], messages,
                    MAX_OUTPUT_TOKENS,
                    self.policy.request_deadline_seconds, event):
                if event.is_set():
                    break
                content += chunk
                sequence += 1
                yield self._event(
                    "text.delta", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "text": chunk,
                    })
                current = time.monotonic()
                if (len(content) - saved_len >= 512
                        or current - saved_at >= 0.5):
                    self._save_partial(request_id, content)
                    saved_len, saved_at = len(content), current
            if event.is_set():
                self._finish(
                    request_id, "stopped", None, content)
                sequence += 1
                yield self._event(
                    "message.interrupted", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "reason": "stopped",
                    })
            else:
                self._finish(
                    request_id, "completed", None, content)
                sequence += 1
                yield self._event(
                    "message.done", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "text_length": len(content),
                    })
        except ChatError as exc:
            self._finish(request_id, "error", exc.code, content)
            sequence += 1
            yield self._event(
                "message.error", {
                    "request_id": str(request_id),
                    "sequence": sequence,
                    "code": exc.code,
                })
        except ProviderFailure as exc:
            self._finish(request_id, "error", exc.code, content)
            sequence += 1
            yield self._event(
                "message.error", {
                    "request_id": str(request_id),
                    "sequence": sequence,
                    "code": exc.code,
                })
        except GeneratorExit:
            self._finish(
                request_id, "interrupted",
                "client_disconnected", content)
            raise
        except Exception:
            self._finish(
                request_id, "error",
                "chat_execution_failed", content)
            sequence += 1
            yield self._event(
                "message.error", {
                    "request_id": str(request_id),
                    "sequence": sequence,
                    "code": "chat_execution_failed",
                })
        finally:
            self._unregister_stop(request_id)

    def _snapshot(self, account_id, request_id):
        with self.engine.begin() as conn:
            row = conn.execute(sa.select(t.requests).where(
                t.requests.c.id == request_id,
                t.requests.c.account_id == account_id)).mappings().first()
            if not row:
                raise ChatError(404, "request_not_found")
            assistant = conn.execute(sa.select(
                t.messages.c.content).where(
                t.messages.c.request_id == request_id,
                t.messages.c.role == "assistant")).scalar_one()
            return dict(row), assistant

    def _follow(self, account_id, request_id):
        sent, sequence = 0, 0
        yield self._event(
            "message.start", {
                "request_id": str(request_id),
                "sequence": sequence,
            })
        while True:
            row, content = self._snapshot(
                account_id, request_id)
            if len(content) > sent:
                sequence += 1
                yield self._event(
                    "text.delta", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "text": content[sent:],
                    })
                sent = len(content)
            state = row["state"]
            if state == "completed":
                sequence += 1
                yield self._event(
                    "message.done", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "text_length": len(content),
                    })
                return
            if state in {"interrupted", "stopped"}:
                sequence += 1
                yield self._event(
                    "message.interrupted", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "reason": state,
                    })
                return
            if state == "error":
                sequence += 1
                yield self._event(
                    "message.error", {
                        "request_id": str(request_id),
                        "sequence": sequence,
                        "code": row["error_code"] or "chat_execution_failed",
                    })
                return
            if self.now() > row["deadline_at"] + 5:
                return
            time.sleep(0.2)
