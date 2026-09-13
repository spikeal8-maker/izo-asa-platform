"""Explicit local owner bootstrap for ACCESS."""
from uuid import UUID

import sqlalchemy as sa

from ..accounts import repository as repo, tables as accounts
from ..accounts.credit_access import verified
from ..accounts.security import AuthError
from . import tables as t
from .permissions import GLOBAL_DELEGABLE


class AccessOwnerMixin:
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
