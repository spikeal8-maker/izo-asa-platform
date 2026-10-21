"""Staff-only DeepSeek platform credential registry, not a Chat execution path."""
import json
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import sqlalchemy as sa
from cryptography.exceptions import InvalidTag

from ..accounts import admin_access as access
from ..accounts.security import AuthError, verify_password
from ..admin import tables as audit
from ..chat.credential_crypto import encrypt, decrypt, operation_fingerprint
from ..chat.provider import ProviderFailure
from ..chat.schemas import ChatSettings
from . import tables as t
from .schemas import ProviderList, ProviderView

PLATFORM_ID = uuid5(NAMESPACE_URL, "izo-asa:platform-credential:deepseek:v1")
# UUID-zero is a deliberate non-account encryption namespace, NOT a user ID.
PLATFORM_NAMESPACE = UUID(int=0)
AAD_PROVIDER = "platform-deepseek"


class PlatformProviderService:
    def __init__(self, auth, provider, policy: ChatSettings | None = None):
        self.auth = auth
        self.provider = provider
        self.policy = policy or ChatSettings()

    def _root(self):
        try:
            return self.policy.root_key_bytes()
        except RuntimeError:
            raise AuthError(503, "credential_storage_unavailable") from None

    @staticmethod
    def _view(row):
        if row is None:
            return ProviderView(configured=False, enabled=False, verified=False,
                status="not_configured", model="deepseek-flash", revision=None,
                generation=None, daily_limit=30, concurrency_limit=1)
        verified = row["verified_at"] is not None
        status = ("not_verified" if not verified else
                  "disabled" if not row["enabled"] else "verified")
        return ProviderView(configured=True, enabled=row["enabled"],
            verified=verified, status=status, model=row["model"],
            revision=row["revision"], generation=row["generation"],
            daily_limit=row["daily_limit"], concurrency_limit=row["concurrency_limit"])

    def _identity(self, conn, raw, permissions, csrf=None, mutation=False):
        return access.staff_session(self.auth, conn, raw, permissions,
                                    csrf=csrf, mutation=mutation)[0]

    def _proof(self, raw, csrf, password, peer, permissions):
        with self.auth.engine.begin() as conn:
            actor = self._identity(conn, raw, permissions, csrf, mutation=True)
            owner, hashed = actor["id"], actor["password_hash"]
        self.auth.throttle("platform-provider:" + str(owner), peer)
        if not verify_password(password, hashed):
            raise AuthError(403, "reauth_required")
        return owner, hashed

    @staticmethod
    def _last_op(row, operation_id, digest):
        if row is None or row["last_operation_id"] != operation_id:
            return False
        if row["last_operation_hash"] != digest:
            raise AuthError(409, "idempotency_conflict")
        return True

    def _event(self, conn, actor, action, operation):
        conn.execute(sa.insert(audit.events).values(
            id=uuid4(), actor_id=actor, action=action, outcome="success",
            operation_id=operation, created_at=self.auth.now()))

    def _authorized(self, conn, raw, csrf, perms, proof):
        actor = self._identity(conn, raw, perms, csrf, mutation=True)
        if actor["id"] != proof[0] or actor["password_hash"] != proof[1]:
            raise AuthError(403, "reauth_required")
        return actor["id"]

    def list(self, raw):
        with self.auth.engine.begin() as conn:
            self._identity(conn, raw, {"connections.read"})
            row = conn.execute(sa.select(t.connections)
                .where(t.connections.c.provider == "deepseek")).mappings().first()
        return ProviderList(connections=[self._view(row)])

    def replace_key(self, raw, csrf, command, peer):
        key = command.key.get_secret_value()
        root = self._root()
        digest = operation_fingerprint(root, "platform:replace:deepseek",
            json.dumps([command.expected_revision, key]).encode("utf-8"))
        perms = {"connections.write", "secrets.bind"}
        proof = self._proof(raw, csrf, command.current_password.get_secret_value(), peer, perms)
        with self.auth.engine.begin() as conn:
            actor = self._authorized(conn, raw, csrf, perms, proof)
            row = conn.execute(sa.select(t.connections).where(
                t.connections.c.provider == "deepseek").with_for_update()).mappings().first()
            if self._last_op(row, command.operation_id, digest):
                return self._view(row)
            if (row is None and command.expected_revision is not None
                    or row is not None and row["revision"] != command.expected_revision):
                raise AuthError(409, "provider_revision_conflict")
            now = self.auth.now()
            generation = row["generation"] + 1 if row else 1
            nonce, ciphertext = encrypt(root, PLATFORM_NAMESPACE, PLATFORM_ID,
                                         generation, key, AAD_PROVIDER)
            values = dict(nonce=nonce, ciphertext=ciphertext, generation=generation,
                revision=row["revision"] + 1 if row else 1, verified_at=None,
                enabled=False, updated_at=now,
                last_operation_id=command.operation_id, last_operation_hash=digest)
            if row:
                conn.execute(sa.update(t.connections)
                    .where(t.connections.c.provider == "deepseek").values(**values))
            else:
                conn.execute(sa.insert(t.connections).values(provider="deepseek",
                    created_at=now, model="deepseek-flash",
                    daily_limit=30, concurrency_limit=1, **values))
            self._event(conn, actor, "platform.key.replaced", command.operation_id)
            return self._view(conn.execute(sa.select(t.connections)).mappings().one())

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
