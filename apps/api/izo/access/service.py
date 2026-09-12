"""Bounded staff delegation with fresh auth and materialized existing permissions."""
from contextlib import contextmanager
from hashlib import sha256
import json
import re
from uuid import UUID, uuid4
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..accounts import admin_access as access, repository as repo, tables as accounts
from ..accounts.credit_access import verified
from ..accounts.security import AuthError, verify_password
from ..admin import tables as admin_tables
from . import tables as t
from .permissions import GLOBAL_DELEGABLE, OWNER_EFFECTIVE
from .schemas import (AccessMe, AccessPermission, AccessReceipt, AccessSubject,
                      GrantAccessInput, RevokeAccessInput)


class AccessService:
    def __init__(self, auth):
        self.auth = auth

    def _event(self, conn, actor, action, *, target=None, outcome="success",
               reference=None, operation=None):
        conn.execute(sa.insert(admin_tables.events).values(id=uuid4(), actor_id=actor,
            target_id=target, action=action, outcome=outcome, case_reference=reference,
            operation_id=operation, created_at=self.auth.now()))

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
        conn.execute(sa.insert(t.operations).values(operation_id=command.operation_id,
            actor_id=actor, target_id=target, action=action, permission=command.permission,
            scope=command.scope, expires_at=expires_at, case_reference=command.case_reference,
            fingerprint=self._fingerprint(action, target, command), created_at=self.auth.now()))
        self._event(conn, actor, "access." + action + "ed", target=target,
                    reference=command.case_reference, operation=command.operation_id)
        return AccessReceipt(operation_id=command.operation_id, target_id=target, action=action,
            permission=command.permission, scope=command.scope, expires_at=expires_at,
            case_reference=command.case_reference)

    def _fresh_proof(self, raw, csrf, password: str, peer: str):
        with self.auth.engine.begin() as conn:
            account, _, _ = access.staff_session(self.auth, conn, raw,
                {"access.manage"}, csrf=csrf, mutation=True)
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

    def me(self, raw) -> AccessMe:
        with self._action(raw, "access.read") as conn:
            actor, session, permissions = access.staff_session(
                self.auth, conn, raw, {"access.read"})
            now = self.auth.now()
            ceiling = conn.execute(sa.select(t.ceilings.c.permission).where(
                t.ceilings.c.account_id == actor["id"], t.ceilings.c.scope == "global",
                sa.or_(t.ceilings.c.expires_at.is_(None), t.ceilings.c.expires_at > now))
                .order_by(t.ceilings.c.permission)).scalars().all()
            return AccessMe(permissions=sorted(permissions),
                delegation_ceiling=list(ceiling), csrf_token=session["csrf_token"])

    def subject(self, raw, target: UUID) -> AccessSubject:
        with self._action(raw, "access.read", target) as conn:
            access.staff_session(self.auth, conn, raw, {"access.read"}, target=target)
            card = access.user_card(conn, target)
            now = self.auth.now()
            rows = conn.execute(sa.select(accounts.permissions).where(
                accounts.permissions.c.account_id == target,
                sa.or_(accounts.permissions.c.expires_at.is_(None),
                       accounts.permissions.c.expires_at > now))
                .order_by(accounts.permissions.c.permission)).mappings().all()
            managed = set(conn.execute(sa.select(t.grants.c.permission).where(
                t.grants.c.account_id == target,
                sa.or_(t.grants.c.expires_at.is_(None), t.grants.c.expires_at > now))).scalars())
            return AccessSubject(id=card["id"], public_code=card["public_code"],
                display_name=card["display_name"], state=card["state"], verified=card["verified"],
                permissions=[AccessPermission(permission=row["permission"],
                    expires_at=row["expires_at"], managed=row["permission"] in managed)
                    for row in rows])

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

    def grant(self, raw, csrf, target: UUID, command: GrantAccessInput, peer: str):
        command = GrantAccessInput.model_validate(command)
        proof_owner, proof_hash = self._fresh_proof(
            raw, csrf, command.current_password.get_secret_value(), peer)
        with self._action(raw, "access.grant", target) as conn:
            actor, _, _ = access.staff_session(self.auth, conn, raw, {"access.manage"},
                target=target, csrf=csrf, mutation=True)
            if actor["id"] != proof_owner or actor["password_hash"] != proof_hash:
                raise AuthError(403, "reauth_required")
            if target == actor["id"]:
                raise AuthError(403, "self_delegation_forbidden")
            replay = self._replay(conn, actor["id"], target, command, "grant")
            if replay is not None:
                return replay
            self._target(conn, target)
            ceiling = self._active_ceiling(conn, actor["id"], command.permission)
            now = self.auth.now()
            expires_at = now + command.ttl_seconds
            if ceiling["expires_at"] is not None and expires_at > ceiling["expires_at"]:
                raise AuthError(403, "delegation_too_long")
            if command.permission == "access.manage":
                read_expiry = conn.execute(sa.select(accounts.permissions.c.expires_at).where(
                    accounts.permissions.c.account_id == target,
                    accounts.permissions.c.permission == "access.read",
                    sa.or_(accounts.permissions.c.expires_at.is_(None),
                           accounts.permissions.c.expires_at >= expires_at))).scalar_one_or_none()
                if read_expiry is None and not conn.execute(sa.select(accounts.permissions.c.account_id).where(
                    accounts.permissions.c.account_id == target,
                    accounts.permissions.c.permission == "access.read",
                    accounts.permissions.c.expires_at.is_(None))).first():
                    raise AuthError(409, "access_read_required")
                self._lock_state(conn)
            grant, materialized = self._existing_rows(conn, target, command.permission)
            if grant is not None:
                active = grant["expires_at"] is None or grant["expires_at"] > now
                if active:
                    raise AuthError(409, "permission_already_granted")
                if materialized is not None and not self._same_materialization(grant, materialized):
                    raise AuthError(409, "permission_provenance_conflict")
                if materialized is not None:
                    conn.execute(sa.delete(accounts.permissions).where(
                        accounts.permissions.c.account_id == target,
                        accounts.permissions.c.permission == command.permission))
                conn.execute(sa.delete(t.grants).where(
                    t.grants.c.account_id == target, t.grants.c.permission == command.permission))
            elif materialized is not None:
                raise AuthError(409, "unmanaged_permission")
            conn.execute(sa.insert(t.grants).values(account_id=target,
                permission=command.permission, scope="global", granted_by=actor["id"],
                created_at=now, expires_at=expires_at))
            conn.execute(sa.insert(accounts.permissions).values(account_id=target,
                permission=command.permission, expires_at=expires_at))
            self._bump_state(conn)
            return self._record_operation(conn, actor["id"], target, command, "grant", expires_at)

    def revoke(self, raw, csrf, target: UUID, command: RevokeAccessInput, peer: str):
        command = RevokeAccessInput.model_validate(command)
        proof_owner, proof_hash = self._fresh_proof(
            raw, csrf, command.current_password.get_secret_value(), peer)
        with self._action(raw, "access.revoke", target) as conn:
            actor, _, _ = access.staff_session(self.auth, conn, raw, {"access.manage"},
                target=target, csrf=csrf, mutation=True)
            if actor["id"] != proof_owner or actor["password_hash"] != proof_hash:
                raise AuthError(403, "reauth_required")
            if target == actor["id"]:
                raise AuthError(403, "self_delegation_forbidden")
            replay = self._replay(conn, actor["id"], target, command, "revoke")
            if replay is not None:
                return replay
            self._active_ceiling(conn, actor["id"], command.permission)
            grant, materialized = self._existing_rows(conn, target, command.permission)
            if grant is None:
                if materialized is not None:
                    raise AuthError(409, "unmanaged_permission")
                raise AuthError(404, "permission_not_granted")
            now = self.auth.now()
            active = grant["expires_at"] is None or grant["expires_at"] > now
            if materialized is not None and not self._same_materialization(grant, materialized):
                raise AuthError(409, "permission_provenance_conflict")
            if active and materialized is None:
                raise AuthError(409, "permission_provenance_conflict")
            if command.permission == "access.read":
                manages = conn.execute(sa.select(accounts.permissions.c.account_id).where(
                    accounts.permissions.c.account_id == target,
                    accounts.permissions.c.permission == "access.manage",
                    sa.or_(accounts.permissions.c.expires_at.is_(None),
                           accounts.permissions.c.expires_at > now))).first()
                if manages is not None:
                    raise AuthError(409, "access_manage_requires_read")
            if command.permission == "access.manage":
                self._lock_state(conn)
                permanent = t.grants.join(t.ceilings, sa.and_(
                    t.ceilings.c.account_id == t.grants.c.account_id,
                    t.ceilings.c.permission == t.grants.c.permission)).join(accounts.permissions, sa.and_(
                    accounts.permissions.c.account_id == t.grants.c.account_id,
                    accounts.permissions.c.permission == t.grants.c.permission)).join(
                    accounts.accounts, accounts.accounts.c.id == t.grants.c.account_id)
                verified_owner = sa.exists(sa.select(accounts.identities.c.id).where(
                    accounts.identities.c.account_id == t.grants.c.account_id,
                    accounts.identities.c.verified_at.is_not(None)))
                remaining = conn.execute(sa.select(sa.func.count()).select_from(permanent).where(
                    t.grants.c.permission == "access.manage", t.grants.c.account_id != target,
                    t.grants.c.expires_at.is_(None), t.ceilings.c.scope == "global",
                    t.ceilings.c.expires_at.is_(None), accounts.permissions.c.expires_at.is_(None),
                    accounts.accounts.c.state == "active", verified_owner)).scalar_one()
                if remaining == 0:
                    raise AuthError(409, "last_access_owner")
            if materialized is not None:
                conn.execute(sa.delete(accounts.permissions).where(
                    accounts.permissions.c.account_id == target,
                    accounts.permissions.c.permission == command.permission))
            conn.execute(sa.delete(t.grants).where(
                t.grants.c.account_id == target, t.grants.c.permission == command.permission))
            self._bump_state(conn)
            return self._record_operation(conn, actor["id"], target, command, "revoke",
                                          grant["expires_at"])

    def enroll_local_owner(self, target: UUID, permissions=GLOBAL_DELEGABLE):
        requested = tuple(dict.fromkeys(permissions))
        if not requested or any(value not in GLOBAL_DELEGABLE for value in requested):
            raise ValueError("Only known global permissions may be bootstrapped")
        with self.auth.engine.begin() as conn:
            account = repo.account_by_id(conn, target, lock=True)
            if not account or account["state"] != "active" or not verified(conn, target):
                raise AuthError(403, "verified_active_account_required")
            existing = conn.execute(sa.select(t.grants.c.permission).where(
                t.grants.c.account_id == target).limit(1)).first()
            existing_ceiling = conn.execute(sa.select(t.ceilings.c.permission).where(
                t.ceilings.c.account_id == target).limit(1)).first()
            if existing or existing_ceiling:
                raise AuthError(409, "access_owner_already_configured")
            state = conn.execute(sa.select(t.state).where(t.state.c.id == 1)
                .with_for_update()).mappings().first()
            if state is None:
                conn.execute(sa.insert(t.state).values(id=1, version=0))
            now = self.auth.now()
            for permission in requested:
                row = conn.execute(sa.select(accounts.permissions).where(
                    accounts.permissions.c.account_id == target,
                    accounts.permissions.c.permission == permission).with_for_update()).mappings().first()
                if row is None:
                    conn.execute(sa.insert(accounts.permissions).values(
                        account_id=target, permission=permission, expires_at=None))
                else:
                    conn.execute(sa.update(accounts.permissions).where(
                        accounts.permissions.c.account_id == target,
                        accounts.permissions.c.permission == permission).values(expires_at=None))
                conn.execute(sa.insert(t.grants).values(account_id=target, permission=permission,
                    scope="global", granted_by=None, created_at=now, expires_at=None))
                conn.execute(sa.insert(t.ceilings).values(account_id=target, permission=permission,
                    scope="global", granted_by=None, created_at=now, expires_at=None))
            self._bump_state(conn)
            self._event(conn, target, "access.local_owner_enrollment", target=target)
