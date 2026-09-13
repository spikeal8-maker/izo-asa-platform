"""Anonymous principal backed by Accounts, isolated from normal account sessions."""
from dataclasses import dataclass, field
import hmac
from uuid import uuid4

import sqlalchemy as sa

from . import guest_tables as gt, repository as repo, tables as t
from .guest_schemas import GuestView
from .guest_settings import GuestSettings
from .schemas import RegisterInput
from .security import AuthError, TOKEN, hash_password, rate_key, token, token_hash


@dataclass(frozen=True)
class GuestReceipt:
    view: GuestView
    bearer: str = field(repr=False)


class GuestService:
    def __init__(self, auth, settings: GuestSettings | None = None):
        self.auth = auth
        self.engine = auth.engine
        self.settings = settings if settings is not None else GuestSettings()

    def now(self) -> int:
        return self.auth.now()

    def _view(self, session) -> GuestView:
        return GuestView(account_id=session["account_id"], csrf_token=session["csrf_token"],
                         expires_at=session["expires_at"],
                         trial_used=session["trial_operation_id"] is not None)

    def _session(self, conn, raw: str | None, csrf: str | None = None, mutation=False):
        self.auth.policy.require_configured()
        self.settings.require_enabled()
        if not raw or not TOKEN.fullmatch(raw):
            raise AuthError(401, "guest_required")
        session = conn.execute(sa.select(gt.sessions).where(
            gt.sessions.c.token_hash == token_hash(raw)).with_for_update()).mappings().first()
        now = self.now()
        if (session is None or session["claimed_at"] is not None or session["expires_at"] <= now
                or session["last_seen_at"] + self.settings.session_seconds <= now):
            raise AuthError(401, "guest_required")
        account = repo.account_by_id(conn, session["account_id"], lock=True)
        if account is None or account["state"] != "active":
            raise AuthError(401, "guest_required")
        identity = conn.execute(sa.select(t.identities.c.verified_at).where(
            t.identities.c.account_id == account["id"],
            t.identities.c.provider == "guest")).scalar_one_or_none()
        if identity is None:
            raise AuthError(401, "guest_required")
        if mutation and (not csrf or not TOKEN.fullmatch(csrf)
                         or not hmac.compare_digest(csrf, session["csrf_token"])):
            raise AuthError(403, "csrf_rejected")
        conn.execute(sa.update(gt.sessions).where(gt.sessions.c.id == session["id"])
                     .values(last_seen_at=now))
        trusted = dict(account)
        trusted["verified_at"] = identity
        return trusted, session

    def me(self, raw: str | None) -> GuestView:
        with self.engine.begin() as conn:
            _, session = self._session(conn, raw)
            return self._view(session)

    def start(self, peer: str, label: str, raw: str | None = None, initializer=None) -> GuestReceipt:
        self.auth.policy.require_configured()
        self.settings.require_enabled()
        if raw:
            try:
                return GuestReceipt(self.me(raw), raw)
            except AuthError as exc:
                if exc.code != "guest_required":
                    raise
        now, window = self.now(), self.settings.rate_window
        start = now - now % window
        secret = self.auth.policy.rate_secret.get_secret_value()
        network_key = rate_key(secret, "guest-network", peer)
        account_id, identity_id, session_id = uuid4(), uuid4(), uuid4()
        bearer, csrf = token(), token()
        with self.engine.begin() as conn:
            count = repo.consume_rate(conn, network_key, start, self.settings.network_limit)
            if count > self.settings.network_limit:
                raise AuthError(429, "guest_rate_limited", start + window - now)
            conn.execute(sa.insert(t.accounts).values(
                id=account_id, public_code=uuid4().hex[:16], display_name="Гость",
                state="active", created_at=now))
            conn.execute(sa.insert(t.identities).values(
                id=identity_id, account_id=account_id, provider="guest",
                subject=uuid4().hex, verified_at=now))
            conn.execute(sa.insert(gt.sessions).values(
                id=session_id, account_id=account_id, token_hash=token_hash(bearer),
                csrf_token=csrf, network_key=network_key, created_at=now, last_seen_at=now,
                expires_at=now + self.settings.session_seconds))
            if initializer is not None:
                initializer(conn, account_id, now)
            repo.event(conn, account_id, "guest.created", now, session_id)
        return GuestReceipt(GuestView(account_id=account_id, csrf_token=csrf,
            expires_at=now + self.settings.session_seconds, trial_used=False), bearer)

    def admission_guard(self, conn, principal, command, draft) -> None:
        if draft.capability_id != "test.image.v1":
            raise AuthError(403, "guest_capability_restricted")
        session = conn.execute(sa.select(gt.sessions).where(
            gt.sessions.c.id == principal.session_id).with_for_update()).mappings().first()
        if session is None or session["claimed_at"] is not None:
            raise AuthError(401, "guest_required")
        used = session["trial_operation_id"]
        if used is not None and used != command.operation_id:
            raise AuthError(409, "guest_trial_used")
        if used is None:
            conn.execute(sa.update(gt.sessions).where(gt.sessions.c.id == session["id"])
                         .values(trial_operation_id=command.operation_id))

    def claim(self, raw: str | None, csrf: str | None, data: RegisterInput,
              peer: str, label: str, guard=None):
        self.auth.throttle(data.email, peer)
        mode = self.auth.policy.registration
        if mode == "disabled":
            raise AuthError(403, "registration_disabled")
        code = data.invite_code.get_secret_value() if data.invite_code else ""
        if mode == "invite" and (not code or not TOKEN.fullmatch(code)):
            raise AuthError(400, "registration_rejected")
        password_hash, now = hash_password(data.password.get_secret_value()), self.now()
        try:
            from sqlalchemy.exc import IntegrityError
            with self.engine.begin() as conn:
                account, session = self._session(conn, raw, csrf, mutation=True)
                if guard is not None:
                    guard(conn, account["id"])
                invitation = None
                if mode == "invite":
                    invitation = conn.execute(sa.select(t.invites).where(
                        t.invites.c.token_hash == token_hash(code)).with_for_update()).mappings().first()
                    if (invitation is None or invitation["consumed_at"] is not None
                            or invitation["expires_at"] <= now):
                        raise AuthError(400, "registration_rejected")
                if repo.account_by_email(conn, data.email):
                    raise AuthError(400, "registration_rejected")
                identity_id = uuid4()
                conn.execute(sa.insert(t.identities).values(
                    id=identity_id, account_id=account["id"], provider="email", subject=data.email))
                conn.execute(sa.insert(t.passwords).values(
                    identity_id=identity_id, password_hash=password_hash))
                conn.execute(sa.update(t.accounts).where(t.accounts.c.id == account["id"])
                             .values(display_name=data.display_name))
                if invitation is not None:
                    conn.execute(sa.update(t.invites).where(t.invites.c.id == invitation["id"])
                                 .values(consumed_at=now, account_id=account["id"]))
                conn.execute(sa.update(gt.sessions).where(gt.sessions.c.id == session["id"])
                             .values(claimed_at=now))
                conn.execute(sa.delete(t.identities).where(
                    t.identities.c.account_id == account["id"], t.identities.c.provider == "guest"))
                repo.event(conn, account["id"], "guest.claimed", now, session["id"])
                claimed = repo.account_by_id(conn, account["id"], lock=True)
                return self.auth._new_session(conn, claimed, label, now)
        except IntegrityError:
            raise AuthError(400, "registration_rejected") from None
