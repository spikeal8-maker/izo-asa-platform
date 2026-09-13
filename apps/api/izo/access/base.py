"""Shared ACCESS service guards, transaction wrappers and operation receipts."""
from contextlib import contextmanager
from hashlib import sha256
import json
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..accounts import admin_access as access, repository as repo, tables as accounts
from ..accounts.credit_access import verified
from ..accounts.security import AuthError, verify_password
from ..admin import tables as admin_tables
from . import tables as t
from .schemas import AccessReceipt


class AccessServiceBase:
    def __init__(self, auth):
        self.auth = auth

    def _event(self, conn, actor, action, *, target=None, outcome="success",
               reference=None, operation=None):
        conn.execute(sa.insert(admin_tables.events).values(
            id=uuid4(), actor_id=actor, target_id=target, action=action, outcome=outcome,
            case_reference=reference, operation_id=operation, created_at=self.auth.now()))

    @contextmanager
    def _action(self, raw, name, target=None):
        try:
            with self.auth.engine.begin() as conn:
                yield conn
        except IntegrityError:
            raise AuthError(409, "access_conflict") from None
        except AuthError as error:
            if error.status != 401:
                with self.auth.engine.begin() as conn:
                    try:
                        owner = access.session_owner(conn, raw)
                    except AuthError:
                        owner = None
                    if owner is not None:
                        self._event(conn, owner, name, target=target, outcome="denied")
            raise

    def _active_ceiling(self, conn, actor: UUID, permission: str):
        now = self.auth.now()
        row = conn.execute(sa.select(t.ceilings).where(
            t.ceilings.c.account_id == actor,
            t.ceilings.c.permission == permission,
            t.ceilings.c.scope == "global",
            sa.or_(t.ceilings.c.expires_at.is_(None), t.ceilings.c.expires_at > now))
            .with_for_update()).mappings().first()
        if row is None:
            raise AuthError(403, "delegation_forbidden")
        return row

    def _target(self, conn, target: UUID):
        account = repo.account_by_id(conn, target)
        if not account:
            raise AuthError(404, "not_found")
        if account["state"] != "active" or not verified(conn, target):
            raise AuthError(403, "verified_active_account_required")
        return account

    @staticmethod
    def _fingerprint(action: str, target: UUID, command) -> str:
        payload = command.model_dump(mode="json", exclude={"current_password"})
        raw = json.dumps({"action": action, "target": str(target), "payload": payload},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return sha256(raw.encode("ascii")).hexdigest()

    def _replay(self, conn, actor: UUID, target: UUID, command, action: str):
        row = conn.execute(sa.select(t.operations).where(
            t.operations.c.operation_id == command.operation_id).with_for_update()).mappings().first()
        if row is None:
            return None
        fingerprint = self._fingerprint(action, target, command)
        if (row["actor_id"] != actor or row["target_id"] != target
                or row["fingerprint"] != fingerprint or row["action"] != action):
            raise AuthError(409, "idempotency_conflict")
        return AccessReceipt(operation_id=row["operation_id"], target_id=row["target_id"],
            action=row["action"], permission=row["permission"], scope=row["scope"],
            expires_at=row["expires_at"], case_reference=row["case_reference"])

    def _record_operation(self, conn, actor, target, command, action, expires_at):
        conn.execute(sa.insert(t.operations).values(
            operation_id=command.operation_id, actor_id=actor, target_id=target, action=action,
            permission=command.permission, scope=command.scope, expires_at=expires_at,
            case_reference=command.case_reference,
            fingerprint=self._fingerprint(action, target, command), created_at=self.auth.now()))
        self._event(conn, actor, "access." + action + "ed", target=target,
                    reference=command.case_reference, operation=command.operation_id)
        return AccessReceipt(operation_id=command.operation_id, target_id=target, action=action,
            permission=command.permission, scope=command.scope, expires_at=expires_at,
            case_reference=command.case_reference)

    def _fresh_proof(self, raw, csrf, password: str, peer: str):
        with self.auth.engine.begin() as conn:
            account, _, _ = access.staff_session(
                self.auth, conn, raw, {"access.manage"}, csrf=csrf, mutation=True)
            owner, encoded = account["id"], account["password_hash"]
        self.auth.throttle("access-manage:" + str(owner), peer)
        if not verify_password(password, encoded):
            raise AuthError(403, "reauth_required")
        return owner, encoded

    @staticmethod
    def _lock_state(conn):
        row = conn.execute(sa.select(t.state).where(t.state.c.id == 1)
            .with_for_update()).mappings().first()
        if row is None:
            raise AuthError(503, "access_state_unavailable")
        return row

    @staticmethod
    def _bump_state(conn):
        conn.execute(sa.update(t.state).where(t.state.c.id == 1)
                     .values(version=t.state.c.version + 1))

    def _existing_rows(self, conn, target: UUID, permission: str):
        grant = conn.execute(sa.select(t.grants).where(
            t.grants.c.account_id == target, t.grants.c.permission == permission)
            .with_for_update()).mappings().first()
        materialized = conn.execute(sa.select(accounts.permissions).where(
            accounts.permissions.c.account_id == target,
            accounts.permissions.c.permission == permission).with_for_update()).mappings().first()
        return grant, materialized

    @staticmethod
    def _same_materialization(grant, materialized) -> bool:
        return bool(grant and materialized and grant["expires_at"] == materialized["expires_at"])
