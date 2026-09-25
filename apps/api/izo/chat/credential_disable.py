"""Provider credential disable path, split from save/verify lifecycle."""
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credential_crypto import operation_fingerprint
from .credential_read import CredentialReadMixin
from .errors import ChatError
from .schemas import CREDENTIAL_WINDOW_LIMIT, CredentialView


class CredentialDisableMixin(CredentialReadMixin):
    def disable_credential(
            self, raw, csrf, command,
            provider: str = "deepseek") -> CredentialView:
        provider = self._provider_id(provider)
        root = self._root()
        op_hash = operation_fingerprint(
            root, f"disable:{provider}",
            f"{command.expected_revision}".encode("ascii"))
        now = self.now()
        streaming: list[UUID] = []
        with self.engine.begin() as conn:
            account, _ = self._account(
                conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"],
                t.connections.c.provider == provider
            ).with_for_update()).mappings().first()
            if not row:
                raise ChatError(409, "credential_not_configured")
            if row["last_operation_id"] == command.operation_id:
                if row["last_operation_hash"] != op_hash:
                    raise ChatError(409, "operation_conflict")
                return self._credential_view(row, provider)
            self._consume_rate(
                conn, account["id"], "credential",
                CREDENTIAL_WINDOW_LIMIT)
            if row["revision"] != command.expected_revision:
                raise ChatError(409, "credential_revision_conflict")
            pending = list(conn.execute(sa.select(
                t.requests.c.id).where(
                    t.requests.c.connection_id == row["id"],
                    t.requests.c.state == "pending")).scalars())
            streaming = list(conn.execute(sa.select(
                t.requests.c.id).where(
                    t.requests.c.connection_id == row["id"],
                    t.requests.c.state == "streaming")).scalars())
            revision = row["revision"] + 1
            conn.execute(sa.update(t.connections).where(
                t.connections.c.id == row["id"]).values(
                enabled=False, verified_at=None,
                revision=revision, updated_at=now,
                last_operation_id=command.operation_id,
                last_operation_hash=op_hash))
            if pending:
                conn.execute(sa.update(t.requests).where(
                    t.requests.c.id.in_(pending)).values(
                    state="stopped",
                    stop_requested_at=now, updated_at=now))
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
            revision=revision, generation=generation,
            provider=provider)
