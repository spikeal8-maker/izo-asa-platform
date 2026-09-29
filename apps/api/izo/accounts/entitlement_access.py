"""Narrow Accounts boundary for plan policy; no credential or role assignment."""
from uuid import UUID
import sqlalchemy as sa
from . import tables as t

metadata = t.metadata


def locked_states(conn, ids: list[UUID]) -> dict[UUID, str]:
    if any(not isinstance(value, UUID) for value in ids):
        raise ValueError("Account IDs must be server-resolved UUIDs")
    ordered = sorted(set(ids), key=lambda value: value.int)
    return dict(conn.execute(sa.select(t.accounts.c.id, t.accounts.c.state)
        .where(t.accounts.c.id.in_(ordered)).order_by(t.accounts.c.id)
        .with_for_update()).all())


def verified(conn, account_id: UUID) -> bool:
    return conn.execute(sa.select(t.identities.c.id).where(
        t.identities.c.account_id == account_id,
        t.identities.c.verified_at.is_not(None)).limit(1)).first() is not None


def may_write(conn, actor_id: UUID, now: int) -> bool:
    return conn.execute(sa.select(t.permissions.c.account_id).where(
        t.permissions.c.account_id == actor_id, t.permissions.c.permission == "plans.write",
        sa.or_(t.permissions.c.expires_at.is_(None), t.permissions.c.expires_at > now))
    ).first() is not None


def record_event(conn, operation_id: UUID, actor_id: UUID, action: str,
                 target_id: UUID | None, now: int) -> None:
    conn.execute(sa.insert(t.audit).values(id=operation_id, account_id=actor_id,
        action="entitlements." + action, target_id=target_id, created_at=now))
