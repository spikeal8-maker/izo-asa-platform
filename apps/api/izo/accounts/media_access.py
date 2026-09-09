"""Narrow Accounts boundary for media. Never accept a client owner or role."""
from dataclasses import dataclass
from uuid import UUID
from .security import AuthError
from .repository import event


@dataclass(frozen=True)
class MediaPrincipal:
    account_id: UUID
    session_id: UUID
    now: int


def context(auth, conn, bearer, csrf=None, *, mutation=False, write=False):
    account, session = auth._session(conn, bearer, csrf, mutation=mutation)
    if account["state"] not in {"active", "generation_suspended"}:
        raise AuthError(403, "account_restricted")
    if write and account["state"] != "active":
        raise AuthError(403, "account_restricted")
    if write and account["verified_at"] is None:
        raise AuthError(403, "verification_required")
    return MediaPrincipal(account["id"], session["id"], auth.now())


def record(conn, principal, action, asset_id):
    event(conn, principal.account_id, action, principal.now, asset_id)


def lock_owner(conn, account_id):
    from .repository import account_by_id
    if account_by_id(conn, account_id, lock=True) is None:
        raise AuthError(404, "not_found")
