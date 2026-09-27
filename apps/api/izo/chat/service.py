"""Compose bounded Chat owners into one request-scoped API service."""
import hashlib
import json
import time
from threading import Event, Lock

import sqlalchemy as sa
from ..catalog.service import CatalogService

from . import tables as t
from .conversations import ConversationMixin
from .credentials import ChatError, CredentialMixin
from .schemas import ChatPolicyView, ModelView
from .schemas import MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS, MODEL_REVISION, REQUEST_WINDOW_SECONDS
from .execution import ExecutionMixin


class ChatService(CredentialMixin, ConversationMixin, ExecutionMixin):
    @staticmethod
    def _request_fingerprint(thread_id, text, model, connection_id, generation,
                             model_revision=MODEL_REVISION) -> str:
        value = {"thread": str(thread_id), "text": text, "model": model,
                 "model_revision": model_revision, "connection": str(connection_id),
                 "credential_generation": generation}
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def __init__(self, auth, policy, provider, clock=time.time):
        self.auth, self.engine, self.policy = auth, auth.engine, policy
        self.provider, self.clock = provider, clock
        self.catalog = CatalogService(auth)
        self._stops: dict[object, Event] = {}
        self._stop_lock = Lock()
        self._recover_stale()

    def now(self) -> int:
        return int(self.clock())

    def _recover_stale(self) -> None:
        now = self.now()
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
            head, models = self.catalog.public_text(conn)
        return ChatPolicyView(
            revision=f"{MODEL_REVISION}:catalog-{head['revision']}",
            default_model=head["default_model"],
            models=[ModelView(id=model.id, label=model.label, provider=model.provider,
                              price=model.price) for model in models],
            max_input_chars=MAX_INPUT_CHARS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    def _root(self) -> bytes:
        try:
            return self.policy.root_key_bytes()
        except RuntimeError:
            raise ChatError(503, "credential_storage_unavailable") from None

    def _snapshot(self, account_id, request_id):
        with self.engine.begin() as conn:
            row = conn.execute(sa.select(t.requests).where(
                t.requests.c.id == request_id,
                t.requests.c.account_id == account_id)).mappings().first()
            if not row:
                raise ChatError(404, "request_not_found")
            assistant = conn.execute(sa.select(t.messages.c.content).where(
                t.messages.c.request_id == request_id,
                t.messages.c.role == "assistant")).scalar_one()
            return dict(row), assistant

    def _follow(self, account_id, request_id):
        sent, sequence = 0, 0
        yield self._event("message.start", {
            "request_id": str(request_id), "sequence": sequence,
        })
        while True:
            row, content = self._snapshot(account_id, request_id)
            if row["state"] in {"pending", "streaming"} and (
                    row["stop_requested_at"] is not None or self.now() >= row["deadline_at"]):
                stopped = row["stop_requested_at"] is not None
                self._finish(request_id, "stopped" if stopped else "interrupted",
                             None if stopped else "request_expired", content)
                continue
            if len(content) > sent:
                sequence += 1
                yield self._event("text.delta", {
                    "request_id": str(request_id), "sequence": sequence,
                    "text": content[sent:],
                })
                sent = len(content)
            state = row["state"]
            if state == "completed":
                sequence += 1
                yield self._event("message.done", {
                    "request_id": str(request_id), "sequence": sequence,
                    "text_length": len(content),
                })
                return
            if state in {"interrupted", "stopped"}:
                sequence += 1
                yield self._event("message.interrupted", {
                    "request_id": str(request_id), "sequence": sequence,
                    "reason": state,
                })
                return
            if state == "error":
                sequence += 1
                yield self._event("message.error", {
                    "request_id": str(request_id), "sequence": sequence,
                    "code": row["error_code"] or "chat_execution_failed",
                })
                return
            time.sleep(0.2)
