"""Narrow Accounts facade for Credits; no passwords, tokens or HTTP identity here."""
from collections.abc import Iterable
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from . import tables as t

# Shared relational metadata is the migration/FK boundary, not a second Account.
metadata = t.metadata


def locked_states(conn: Connection, account_ids: Iterable[UUID]) -> dict[UUID, str]:
    """Lock all affected Accounts in one consistent order before any wallet.

    A future staff HTTP command must use this order before locking its session;
    it must not authenticate with a held actor lock then lock a lower target ID.
    """
    ids = sorted(set(account_ids), key=lambda value: value.int)
    rows = conn.execute(sa.select(t.accounts.c.id, t.accounts.c.state)
        .where(t.accounts.c.id.in_(ids)).order_by(t.accounts.c.id).with_for_update()).all()
    return dict(rows)


def verified(conn: Connection, account_id: UUID) -> bool:
    return conn.execute(sa.select(t.identities.c.id).where(
        t.identities.c.account_id == account_id, t.identities.c.verified_at.is_not(None))
        .limit(1)).first() is not None


def may_grant(conn: Connection, actor_id: UUID, now: int) -> bool:
    return conn.execute(sa.select(t.permissions.c.account_id).where(
        t.permissions.c.account_id == actor_id,
        t.permissions.c.permission == "credits.grant",
        sa.or_(t.permissions.c.expires_at.is_(None), t.permissions.c.expires_at > now))
    ).first() is not None


def record_event(conn: Connection, account_id: UUID, action: str,
                 entry_id: UUID, now: int) -> None:
    conn.execute(sa.insert(t.audit).values(id=uuid4(), account_id=account_id,
        action="credits." + action, target_id=entry_id, created_at=now))
