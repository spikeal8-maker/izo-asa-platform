"""ACCESS grant/revoke mutations."""
from uuid import UUID

import sqlalchemy as sa

from ..accounts import admin_access as access, tables as accounts
from ..accounts.security import AuthError
from . import tables as t
from .schemas import GrantAccessInput, RevokeAccessInput


class AccessMutationMixin:
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
