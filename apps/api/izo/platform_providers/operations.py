"""Operations for platform-owned provider verification and policy update."""
import json
from functools import wraps
from uuid import uuid4

import sqlalchemy as sa
from cryptography.exceptions import InvalidTag

from ..accounts import admin_access as access
from ..accounts.security import AuthError
from ..admin import tables as audit
from ..chat.credential_crypto import decrypt, operation_fingerprint
from ..chat.provider import ProviderFailure
from . import tables as t
from .namespace import PLATFORM_ID, PLATFORM_NAMESPACE, AAD_PROVIDER


def audit_denials(action):
    """Record known-actor failures after the failed mutation has rolled back."""
    def decorated(fn):
        @wraps(fn)
        def run(self, raw, csrf, command, peer):
            try:
                return fn(self, raw, csrf, command, peer)
            except AuthError as error:
                if error.status != 401:
                    self._audit_denied(raw, action)
                raise
        return run
    return decorated


class ProviderOperationsMixin:
    def _audit_denied(self, raw, action):
        # A separate transaction avoids losing evidence when a mutation rolls back.
        # No password, key, request body, or user-selected operation UUID is recorded.
        try:
            with self.auth.engine.begin() as conn:
                actor = access.session_owner(conn, raw)
                conn.execute(sa.insert(audit.events).values(
                    id=uuid4(), actor_id=actor, action=action, outcome="denied",
                    created_at=self.auth.now()))
        except (AuthError, sa.exc.SQLAlchemyError):
            pass  # Preserve the original denial on invalid/revoked sessions or DB outage.

    @audit_denials("platform.key.verified")
    def verify(self, raw, csrf, command, peer):
        root = self._root()
        digest = operation_fingerprint(root, "platform:verify:deepseek",
                                       str(command.expected_revision).encode("ascii"))
        perms = {"connections.write", "secrets.bind"}
        proof = self._proof(raw, csrf, command.current_password.get_secret_value(), peer, perms)
        with self.auth.engine.begin() as conn:
            self._authorized(conn, raw, csrf, perms, proof)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.provider == "deepseek")).mappings().first()
            if row is None:
                raise AuthError(409, "provider_not_configured")
            if self._last_op(row, command.operation_id, digest):
                return self._view(row)
            if row["revision"] != command.expected_revision:
                raise AuthError(409, "provider_revision_conflict")
            try:
                key = decrypt(root, PLATFORM_NAMESPACE, PLATFORM_ID,
                    row["generation"], row["nonce"], row["ciphertext"], AAD_PROVIDER)
            except (InvalidTag, UnicodeError, ValueError):
                raise AuthError(503, "credential_unavailable") from None
            generation = row["generation"]
        try:
            self.provider.verify(key, timeout=15)
        except ProviderFailure as exc:
            status = 422 if exc.code == "credential_rejected" else 503
            raise AuthError(status, exc.code) from None
        finally:
            key = None
        with self.auth.engine.begin() as conn:
            actor = self._authorized(conn, raw, csrf, perms, proof)
            current = conn.execute(sa.select(t.connections).where(
                t.connections.c.provider == "deepseek").with_for_update()).mappings().first()
            # A matching request may have committed while this probe was in flight.
            if self._last_op(current, command.operation_id, digest):
                return self._view(current)
            if (current is None or current["revision"] != command.expected_revision
                    or current["generation"] != generation):
                raise AuthError(409, "provider_changed_during_verify")
            conn.execute(sa.update(t.connections).where(
                t.connections.c.provider == "deepseek").values(
                revision=current["revision"] + 1, verified_at=self.auth.now(),
                updated_at=self.auth.now(),
                last_operation_id=command.operation_id, last_operation_hash=digest))
            self._event(conn, actor, "platform.key.verified", command.operation_id)
            return self._view(conn.execute(sa.select(t.connections)).mappings().one())

    @audit_denials("platform.policy.changed")
    def configure(self, raw, csrf, command, peer):
        root = self._root()
        payload = command.model_dump(mode="json", exclude={"current_password", "operation_id"})
        digest = operation_fingerprint(root, "platform:policy:deepseek",
            json.dumps(payload, sort_keys=True).encode("utf-8"))
        perms = {"connections.write"}
        proof = self._proof(raw, csrf, command.current_password.get_secret_value(), peer, perms)
        with self.auth.engine.begin() as conn:
            actor = self._authorized(conn, raw, csrf, perms, proof)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.provider == "deepseek").with_for_update()).mappings().first()
            if row is None:
                raise AuthError(409, "provider_not_configured")
            if self._last_op(row, command.operation_id, digest):
                return self._view(row)
            if row["revision"] != command.expected_revision:
                raise AuthError(409, "provider_revision_conflict")
            if command.enabled and row["verified_at"] is None:
                raise AuthError(409, "provider_not_verified")
            conn.execute(sa.update(t.connections).where(
                t.connections.c.provider == "deepseek").values(
                model=command.model, enabled=command.enabled,
                daily_limit=command.daily_limit,
                concurrency_limit=command.concurrency_limit,
                revision=row["revision"] + 1, updated_at=self.auth.now(),
                last_operation_id=command.operation_id, last_operation_hash=digest))
            self._event(conn, actor, "platform.policy.changed", command.operation_id)
            return self._view(conn.execute(sa.select(t.connections)).mappings().one())
