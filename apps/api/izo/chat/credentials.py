"""Account-owned provider-aware Chat credential lifecycle."""
from uuid import uuid4

import sqlalchemy as sa
from cryptography.exceptions import InvalidTag

from . import tables as t
from .credential_crypto import decrypt, encrypt, operation_fingerprint
from .credential_disable import CredentialDisableMixin
from .errors import ChatError
from .provider import ProviderFailure
from .schemas import CREDENTIAL_WINDOW_LIMIT, CredentialView
class CredentialMixin(CredentialDisableMixin):
    def save_credential(
            self, raw, csrf, command,
            provider: str = "deepseek") -> CredentialView:
        provider = self._provider_id(provider)
        root = self._root()
        key = command.key.get_secret_value()
        operation_hash = operation_fingerprint(
            root, f"save:{provider}",
            (str(command.expected_revision) + "\0" + key).encode("utf-8"))
        now = self.now()
        with self.engine.begin() as conn:
            account, _ = self._account(
                conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"],
                t.connections.c.provider == provider
            ).with_for_update()).mappings().first()
            if row and row["last_operation_id"] == command.operation_id:
                if row["last_operation_hash"] != operation_hash:
                    raise ChatError(409, "operation_conflict")
                return self._credential_view(row, provider)
            self._consume_rate(
                conn, account["id"], "credential",
                CREDENTIAL_WINDOW_LIMIT, required_slots=2)
            if row and command.expected_revision != row["revision"]:
                raise ChatError(
                    409, "credential_revision_conflict")
            if not row and command.expected_revision is not None:
                raise ChatError(
                    409, "credential_revision_conflict")
            if row and self._active_for_connection(conn, row["id"]):
                raise ChatError(409, "credential_in_use")
            connection_id = row["id"] if row else uuid4()
            generation = row["generation"] + 1 if row else 1
            revision = row["revision"] + 1 if row else 1
            nonce, ciphertext = encrypt(
                root, account["id"], connection_id, generation,
                key, provider)
            values = dict(
                provider=provider, generation=generation,
                revision=revision, nonce=nonce,
                ciphertext=ciphertext, enabled=True,
                verified_at=None,
                last_operation_id=command.operation_id,
                last_operation_hash=operation_hash,
                updated_at=now)
            if row:
                conn.execute(sa.update(t.connections).where(
                    t.connections.c.id == connection_id
                ).values(**values))
            else:
                conn.execute(sa.insert(t.connections).values(
                    id=connection_id, account_id=account["id"],
                    created_at=now, **values))
            return CredentialView(
                configured=True, enabled=True, verified=False,
                revision=revision, generation=generation,
                provider=provider)

    def verify_credential(
            self, raw, csrf, command,
            provider: str = "deepseek") -> CredentialView:
        provider = self._provider_id(provider)
        root = self._root()
        op_hash = operation_fingerprint(
            root, f"verify:{provider}",
            f"{command.expected_revision}".encode("ascii"))
        with self.engine.begin() as conn:
            account, _ = self._account(
                conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"],
                t.connections.c.provider == provider
            ).with_for_update()).mappings().first()
            if not row or not row["enabled"]:
                raise ChatError(
                    409, "credential_not_configured")
            if row["last_operation_id"] == command.operation_id:
                if row["last_operation_hash"] != op_hash:
                    raise ChatError(409, "operation_conflict")
                return self._credential_view(row, provider)
            self._consume_rate(
                conn, account["id"], "credential",
                CREDENTIAL_WINDOW_LIMIT)
            if row["revision"] != command.expected_revision:
                raise ChatError(
                    409, "credential_revision_conflict")
            snapshot = dict(row)
            try:
                key = decrypt(
                    root, account["id"], row["id"],
                    row["generation"], row["nonce"],
                    row["ciphertext"], provider)
            except (InvalidTag, UnicodeError, ValueError):
                raise ChatError(
                    503, "credential_unavailable") from None
        try:
            self.provider_for(provider).verify(
                key, timeout=min(
                    15, self.policy.request_deadline_seconds))
        except ProviderFailure as exc:
            status = 422 if exc.code == "credential_rejected" else 503
            raise ChatError(status, exc.code) from None
        now = self.now()
        with self.engine.begin() as conn:
            account, _ = self._account(
                conn, raw, csrf, mutation=True)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.account_id == account["id"],
                t.connections.c.provider == provider
            ).with_for_update()).mappings().first()
            if (not row or row["id"] != snapshot["id"]
                    or row["revision"] != snapshot["revision"]
                    or row["generation"] != snapshot["generation"]):
                raise ChatError(409, "credential_changed")
            revision = row["revision"] + 1
            conn.execute(sa.update(t.connections).where(
                t.connections.c.id == row["id"]).values(
                verified_at=now, revision=revision,
                updated_at=now,
                last_operation_id=command.operation_id,
                last_operation_hash=op_hash))
            return CredentialView(
                configured=True, enabled=True, verified=True,
                revision=revision,
                generation=row["generation"], provider=provider)
