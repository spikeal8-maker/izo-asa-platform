"""Read-only ACCESS projections."""
from uuid import UUID

import sqlalchemy as sa

from ..accounts import admin_access as access, tables as accounts
from . import tables as t
from .schemas import AccessMe, AccessPermission, AccessSubject


class AccessReadMixin:
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
