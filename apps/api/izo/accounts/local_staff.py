"""Exact-account staff identity exception for an explicitly isolated local preview."""
import os
from uuid import UUID

import sqlalchemy as sa

from . import tables as t
from .credit_access import verified


def verified_only_staff_permission(permission: str) -> bool:
    return permission.startswith(("credits.", "plans."))


def local_unverified_staff_account_id() -> UUID | None:
    if os.getenv("IZO_ENVIRONMENT") not in {"development", "test"}:
        return None
    if os.getenv("IZO_LOCAL_UNVERIFIED_STAFF_MODE") != "isolated":
        return None
    raw = os.getenv("IZO_LOCAL_UNVERIFIED_STAFF_ACCOUNT_ID", "")
    try:
        account_id = UUID(raw)
    except (TypeError, ValueError, AttributeError):
        return None
    return account_id if raw == str(account_id) else None


def staff_identity_allowed(conn, account_id: UUID) -> bool:
    # This does not certify the mailbox or change the account's verified_at.
    if verified(conn, account_id):
        return True
    if local_unverified_staff_account_id() != account_id:
        return False
    return conn.execute(sa.select(t.identities.c.id).where(
        t.identities.c.account_id == account_id,
        t.identities.c.provider == "email").limit(1)).first() is not None
