"""Compose bounded Chat owners into one request-scoped API service."""
import time
from uuid import uuid4
from threading import Event, Lock

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..accounts import repository as account_repo, tables as account_tables

from . import tables as t
from .conversations import ConversationMixin
from .credentials import ChatError, CredentialMixin
from .schemas import ChatPolicyView, ModelView
from .schemas import (
    DEFAULT_MODEL, MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS, MODEL_REVISION,
    MODELS, REQUEST_WINDOW_SECONDS,
)
from .execution import ExecutionMixin


class ChatService(CredentialMixin, ConversationMixin, ExecutionMixin):
    def __init__(self, auth, policy, provider, clock=time.time):
        self.auth, self.engine, self.policy = auth, auth.engine, policy
        self.provider, self.clock = provider, clock
        self._stops: dict[object, Event] = {}
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
            # OpenAPI composition stays side-effect free when no DB is running.
            pass

    def local_preview_session(self, label: str):
        email, now = "preview@local.izo", self.auth.now()
        try:
            with self.engine.begin() as conn:
                account = account_repo.account_by_email(conn, email)
                if account is None:
                    account_id, identity_id = uuid4(), uuid4()
                    conn.execute(account_tables.accounts.insert().values(
                        id=account_id, public_code=uuid4().hex[:16],
                        display_name="Local Preview", state="active", created_at=now))
                    conn.execute(account_tables.identities.insert().values(
                        id=identity_id, account_id=account_id, provider="email",
                        subject=email, verified_at=now))
                    account_repo.event(conn, account_id, "account.local_preview_created", now)
                    account = account_repo.account_by_id(conn, account_id, lock=True)
                if not account or account["state"] != "active":
                    raise ChatError(403, "local_preview_account_unavailable")
                return self.auth._new_session(conn, account, label, now)
        except IntegrityError:
            with self.engine.begin() as conn:
                account = account_repo.account_by_email(conn, email)
                if not account or account["state"] != "active":
                    raise ChatError(403, "local_preview_account_unavailable") from None
                return self.auth._new_session(conn, account, label, self.auth.now())

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

    def _root(self) -> bytes:
        try:
            return self.policy.root_key_bytes()
        except RuntimeError:
            raise ChatError(503, "credential_storage_unavailable") from None
