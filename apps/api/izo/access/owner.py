"""Explicit local owner bootstrap for ACCESS."""
import os
from uuid import UUID

import sqlalchemy as sa

from ..accounts import repository as repo, tables as accounts
from ..accounts.credit_access import verified
from ..accounts.security import AuthError
from ..config import Settings
from . import tables as t
from .permissions import GLOBAL_DELEGABLE


class AccessOwnerMixin:
    def upgrade_local_owner_permission(self, target: UUID, permission: str) -> bool:
        """Explicit isolated upgrade for owners enrolled before pricing.write existed."""
        if permission != "pricing.write":
            raise ValueError("Only the reviewed pricing permission can be upgraded")
        if (Settings().environment not in {"development", "test"}
                or os.getenv("IZO_ACCESS_BOOTSTRAP") != "isolated"):
            raise AuthError(403, "local_upgrade_disabled")
        with self.auth.engine.begin() as conn:
            account = repo.account_by_id(conn, target, lock=True)
            if not account or account["state"] != "active" or not verified(conn, target):
                raise AuthError(403, "access_owner_required")
            self._lock_state(conn)

            def current(table, name):
                return conn.execute(sa.select(table).where(
                    table.c.account_id == target, table.c.permission == name)
                    .with_for_update()).mappings().first()

            grant = current(t.grants, "access.manage")
            ceiling = current(t.ceilings, "access.manage")
            materialized = current(accounts.permissions, "access.manage")
            if not (grant and ceiling and materialized
                    and grant["scope"] == ceiling["scope"] == "global"
                    and grant["granted_by"] is None and ceiling["granted_by"] is None
                    and grant["expires_at"] is None and ceiling["expires_at"] is None
                    and materialized["expires_at"] is None):
                raise AuthError(403, "access_owner_required")
            grant = current(t.grants, permission)
            ceiling = current(t.ceilings, permission)
            materialized = current(accounts.permissions, permission)
            if any((grant, ceiling, materialized)):
                if (grant and ceiling and materialized
                        and grant["scope"] == ceiling["scope"] == "global"
                        and grant["granted_by"] is None and ceiling["granted_by"] is None
                        and grant["expires_at"] is None and ceiling["expires_at"] is None
                        and materialized["expires_at"] is None):
                    return False
                raise AuthError(409, "permission_provenance_conflict")
            now = self.auth.now()
            conn.execute(sa.insert(accounts.permissions).values(
                account_id=target, permission=permission, expires_at=None))
            conn.execute(sa.insert(t.grants).values(account_id=target, permission=permission,
                scope="global", granted_by=None, created_at=now, expires_at=None))
            conn.execute(sa.insert(t.ceilings).values(account_id=target, permission=permission,
                scope="global", granted_by=None, created_at=now, expires_at=None))
            self._bump_state(conn)
            self._event(conn, target, "access.local_owner_upgrade", target=target,
                        reference=permission)
            return True

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
                conn.execute(sa.insert(t.grants).values(
                    account_id=target, permission=permission, scope="global", granted_by=None,
                    created_at=now, expires_at=None))
                conn.execute(sa.insert(t.ceilings).values(
                    account_id=target, permission=permission, scope="global", granted_by=None,
                    created_at=now, expires_at=None))
            self._bump_state(conn)
            self._event(conn, target, "access.local_owner_enrollment", target=target)
