"""Accounts-owned facade: staff identity, stable lock order and redacted queries."""
from dataclasses import dataclass, field
from uuid import UUID
import sqlalchemy as sa

from . import repository as repo, tables as t
from .credit_access import locked_states, verified
from .security import AuthError, TOKEN, token_hash, verify_password

metadata = t.metadata


def session_owner(conn, raw: str | None) -> UUID:
    if not raw or not TOKEN.fullmatch(raw):
        raise AuthError(401, "auth_required")
    owner = conn.execute(sa.select(t.sessions.c.account_id).where(
        t.sessions.c.token_hash == token_hash(raw))).scalar_one_or_none()
    if owner is None:
        raise AuthError(401, "auth_required")
    return owner


def staff_session(auth, conn, raw, required, *, target=None, csrf=None, mutation=False):
    """All Account locks precede session and wallet locks; no actor-first inversion."""
    owner = session_owner(conn, raw)
    # Early deny avoids locking an unrelated target for an ordinary account.
    # This is not the authoritative grant: permission rows are checked again below.
    if not set(required).issubset(set(repo.grant_names(conn, owner, auth.now()))):
        raise AuthError(403, "forbidden")
    locked_states(conn, [owner] if target is None else [owner, target])
    account, session = auth._session(conn, raw, csrf, mutation=mutation)
    permissions = set(conn.execute(sa.select(t.permissions.c.permission).where(
        t.permissions.c.account_id == owner,
        sa.or_(t.permissions.c.expires_at.is_(None), t.permissions.c.expires_at > auth.now()))
        .with_for_update(read=True)).scalars())
    if account["state"] != "active" or not set(required).issubset(permissions):
        raise AuthError(403, "forbidden")
    if not verified(conn, owner):
        raise AuthError(403, "verification_required")
    return account, session, permissions


@dataclass(frozen=True)
class PasswordProof:
    owner_id: UUID
    encoded: str = field(repr=False)


def reauthenticate(auth, raw, csrf, password: str, peer: str) -> PasswordProof:
    # Bounded KDF outside long-lived locks. Re-check exact credential/session in
    # the final transaction so concurrent reset/revoke/permission change wins.
    with auth.engine.begin() as conn:
        account, _, _ = staff_session(auth, conn, raw,
            {"users.read_limited", "credits.read", "credits.grant"}, csrf=csrf, mutation=True)
        proof = PasswordProof(account["id"], account["password_hash"])
    auth.throttle("admin-compensation:" + str(proof.owner_id), peer)
    if not verify_password(password, proof.encoded):
        raise AuthError(403, "reauth_required")
    return proof


def public_query():
    is_verified = sa.exists(sa.select(t.identities.c.id).where(
        t.identities.c.account_id == t.accounts.c.id, t.identities.c.verified_at.is_not(None)))
    return sa.select(t.accounts.c.id, t.accounts.c.public_code, t.accounts.c.display_name,
                     t.accounts.c.state, t.accounts.c.created_at, is_verified.label("verified"))


def search_users(conn, query: str, limit: int, after: UUID | None):
    statement = public_query().where(sa.or_(t.accounts.c.public_code == query.lower(),
        sa.func.lower(t.accounts.c.display_name).contains(query.lower(), autoescape=True)))
    if after:
        statement = statement.where(t.accounts.c.id > after)
    return conn.execute(statement.order_by(t.accounts.c.id).limit(limit + 1)).mappings().all()


def user_card(conn, target: UUID):
    row = conn.execute(public_query().where(t.accounts.c.id == target)).mappings().first()
    if row is None:
        raise AuthError(404, "not_found")
    return dict(row)


def enroll_local_operator(conn, target: UUID, permissions: tuple[str, ...], now: int):
    """Local operator-only provisioning, not an HTTP role assignment command."""
    account = repo.account_by_id(conn, target, lock=True)
    if not account or account["state"] != "active" or not verified(conn, target):
        raise AuthError(403, "verified_active_account_required")
    existing = set(conn.execute(sa.select(t.permissions.c.permission).where(
        t.permissions.c.account_id == target)).scalars())
    if any(permission in existing for permission in permissions):
        raise AuthError(409, "operator_already_configured")
    for permission in permissions:
        conn.execute(sa.insert(t.permissions).values(account_id=target, permission=permission))
    repo.event(conn, target, "admin.local_enrollment", now)
