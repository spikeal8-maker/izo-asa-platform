"""Accounts-owned locks for jobs; worker IDs are never browser credentials."""
import sqlalchemy as sa
from . import tables as t
from .credit_access import verified
from .media_access import context


def lock_worker_owner(conn, owner, *, skip_locked=False):
    # A worker MUST acquire Accounts before Jobs; inverted ordering deadlocks
    # against a browser cancel or a grant already holding the account lock.
    row = conn.execute(sa.select(t.accounts.c.id, t.accounts.c.state)
        .where(t.accounts.c.id == owner).with_for_update(skip_locked=skip_locked)).mappings().first()
    if row is None:
        return None
    return row["state"] if verified(conn, owner) else "unverified"


__all__ = ["context", "lock_worker_owner"]
