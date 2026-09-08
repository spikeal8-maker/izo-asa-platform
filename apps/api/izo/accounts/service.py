"""Real server account/session commands; all state belongs to the database."""
from dataclasses import dataclass, field
import hmac
import time
from uuid import UUID, uuid4
from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from . import repository as repo, tables as t
from .schemas import AccountView, AuthView, LoginInput, RegisterInput, SessionList, SessionView
from .security import AuthError, TOKEN, hash_password, rate_key, token, token_hash, verify_password
from .settings import AuthSettings


@dataclass
class Receipt:
    view: AuthView
    bearer: str = field(repr=False)


class AuthService:
    def __init__(self, engine, policy: AuthSettings, clock: Callable[[], float] = time.time):
        self.engine, self.policy, self.clock = engine, policy, clock

    def now(self) -> int:
        return int(self.clock())

    def throttle(self, email: str, peer: str) -> None:
        self.policy.require_configured()
        now, window = self.now(), self.policy.rate_window
        start = now - now % window
        secret = self.policy.rate_secret.get_secret_value()
        # Fixed-window counters are committed even when login fails. No raw PII.
        with self.engine.begin() as conn:
            network = repo.consume_rate(conn, rate_key(secret, "network", peer), start,
                                        self.policy.network_limit)
            identity = repo.consume_rate(conn, rate_key(secret, "identity", email), start,
                                         self.policy.login_limit)
            conn.execute(sa.delete(t.limits).where(t.limits.c.window_start < start - 2 * window))
        if network > self.policy.network_limit or identity > self.policy.login_limit:
            raise AuthError(429, "rate_limited", start + window - now)

    def issue_invite(self, ttl_seconds: int = 86400) -> str:
        """Operator/isolated test command; deliberately not exposed by public HTTP."""
        if not 60 <= ttl_seconds <= 604800:
            raise ValueError("Invite lifetime out of range")
        now, raw, invite_id = self.now(), token(), uuid4()
        with self.engine.begin() as conn:
            conn.execute(sa.insert(t.invites).values(id=invite_id, token_hash=token_hash(raw),
                created_at=now, expires_at=now + ttl_seconds))
            repo.event(conn, None, "invite.created", now, invite_id)
        return raw

    def _view(self, conn, account, csrf: str) -> AuthView:
        return AuthView(account=AccountView(id=account["id"], public_code=account["public_code"],
            display_name=account["display_name"], email=account["email"],
            email_verified=account["verified_at"] is not None, state=account["state"],
            permissions=repo.grant_names(conn, account["id"], self.now())), csrf_token=csrf)

    def _new_session(self, conn, account, label: str, now: int) -> Receipt:
        # Caller holds account row lock: concurrent logins respect the cap.
        active = self._active_sessions(conn, account["id"], now)
        if len(active) >= self.policy.max_sessions:
            raise AuthError(409, "session_limit")
        raw, csrf, session_id = token(), token(), uuid4()
        safe_label = "".join(c for c in label if c.isprintable())[:160] or "Unknown client"
        conn.execute(sa.insert(t.sessions).values(id=session_id, account_id=account["id"],
            token_hash=token_hash(raw), csrf_token=csrf, created_at=now, last_seen_at=now,
            expires_at=now + self.policy.absolute_seconds, idle_seconds=self.policy.idle_seconds,
            client_label=safe_label))
        repo.event(conn, account["id"], "session.created", now, session_id)
        return Receipt(self._view(conn, account, csrf), raw)

    def register(self, data: RegisterInput, peer: str, label: str) -> Receipt:
        self.throttle(data.email, peer)
        if self.policy.registration != "invite":
            raise AuthError(403, "registration_disabled")
        code = data.invite_code.get_secret_value()
        if not TOKEN.fullmatch(code):
            raise AuthError(400, "registration_rejected")
        password_hash = hash_password(data.password.get_secret_value())
        now, account_id, identity_id = self.now(), uuid4(), uuid4()
        try:
            with self.engine.begin() as conn:
                invitation = conn.execute(sa.select(t.invites).where(
                    t.invites.c.token_hash == token_hash(code)).with_for_update()).mappings().first()
                if (not invitation or invitation["consumed_at"] is not None
                        or invitation["expires_at"] <= now or repo.account_by_email(conn, data.email)):
                    raise AuthError(400, "registration_rejected")
                conn.execute(sa.insert(t.accounts).values(id=account_id, public_code=uuid4().hex[:16],
                    display_name=data.display_name, state="active", created_at=now))
                conn.execute(sa.insert(t.identities).values(id=identity_id, account_id=account_id,
                    provider="email", subject=data.email))
                conn.execute(sa.insert(t.passwords).values(identity_id=identity_id, password_hash=password_hash))
                conn.execute(sa.update(t.invites).where(t.invites.c.id == invitation["id"]).values(
                    consumed_at=now, account_id=account_id))
                repo.event(conn, account_id, "account.registered", now)
                account = repo.account_by_id(conn, account_id, lock=True)
                return self._new_session(conn, account, label, now)
        except IntegrityError:
            # Duplicate identities roll back invitation consumption and every new row.
            raise AuthError(400, "registration_rejected") from None

    def login(self, data: LoginInput, peer: str, label: str) -> Receipt:
        self.throttle(data.email, peer)
        with self.engine.begin() as conn:
            account = repo.account_by_email(conn, data.email)
        encoded = account["password_hash"] if account else None
        valid = verify_password(data.password.get_secret_value(), encoded)
        if not valid or not account:
            raise AuthError(401, "invalid_credentials")
        with self.engine.begin() as conn:
            current = repo.account_by_id(conn, account["id"], lock=True)
            if (not current or current["password_hash"] != encoded
                    or current["state"] not in {"active", "generation_suspended"}):
                raise AuthError(401, "invalid_credentials")
            return self._new_session(conn, current, label, self.now())

    def _session(self, conn, raw: str | None, csrf: str | None = None, mutation=False):
        self.policy.require_configured()
        if not raw or not TOKEN.fullmatch(raw):
            raise AuthError(401, "auth_required")
        row = conn.execute(sa.select(t.sessions).where(
            t.sessions.c.token_hash == token_hash(raw))).mappings().first()
        if not row:
            raise AuthError(401, "auth_required")
        # Consistent account->session lock order shared by login/revoke operations.
        account = repo.account_by_id(conn, row["account_id"], lock=True)
        row = conn.execute(sa.select(t.sessions).where(t.sessions.c.id == row["id"])
                           .with_for_update()).mappings().first()
        now = self.now()
        if (not row or row["revoked_at"] is not None or row["expires_at"] <= now
                or row["last_seen_at"] + min(row["idle_seconds"], self.policy.idle_seconds) <= now
                or row["created_at"] + self.policy.absolute_seconds <= now
                or not account or account["state"] not in {"active", "generation_suspended", "deletion_pending"}):
            raise AuthError(401, "auth_required")
        if mutation and (not csrf or not TOKEN.fullmatch(csrf) or not hmac.compare_digest(csrf, row["csrf_token"])):
            raise AuthError(403, "csrf_rejected")
        conn.execute(sa.update(t.sessions).where(t.sessions.c.id == row["id"]).values(last_seen_at=now))
        return account, row

    def me(self, raw: str | None) -> AuthView:
        with self.engine.begin() as conn:
            account, session = self._session(conn, raw)
            return self._view(conn, account, session["csrf_token"])

    def _active_sessions(self, conn, account_id, now):
        return conn.execute(sa.select(t.sessions).where(t.sessions.c.account_id == account_id,
            t.sessions.c.revoked_at.is_(None), t.sessions.c.expires_at > now,
            t.sessions.c.created_at + self.policy.absolute_seconds > now,
            t.sessions.c.last_seen_at + t.sessions.c.idle_seconds > now,
            t.sessions.c.last_seen_at + self.policy.idle_seconds > now
        ).order_by(t.sessions.c.created_at, t.sessions.c.id)).mappings().all()

    def list_sessions(self, raw: str | None) -> SessionList:
        with self.engine.begin() as conn:
            account, current = self._session(conn, raw)
            return SessionList(sessions=[SessionView(id=s["id"], created_at=s["created_at"],
                last_seen_at=s["last_seen_at"], expires_at=min(s["expires_at"],
                s["created_at"] + self.policy.absolute_seconds), client_label=s["client_label"],
                current=s["id"] == current["id"]) for s in self._active_sessions(conn, account["id"], self.now())])

    def revoke(self, raw: str | None, csrf: str | None, target: UUID | None = None,
               others: bool = False) -> bool:
        with self.engine.begin() as conn:
            account, current = self._session(conn, raw, csrf, mutation=True)
            query = sa.update(t.sessions).where(t.sessions.c.account_id == account["id"])
            if others:
                query = query.where(t.sessions.c.id != current["id"], t.sessions.c.revoked_at.is_(None))
            else:
                target = target or current["id"]
                query = query.where(t.sessions.c.id == target)
            result = conn.execute(query.values(revoked_at=self.now()))
            if not others and result.rowcount == 0:
                raise AuthError(404, "not_found")
            repo.event(conn, account["id"], "sessions.revoke_others" if others else "session.revoked",
                       self.now(), target)
            return not others and target == current["id"]

    def require_permission(self, raw: str | None, permission: str) -> AccountView:
        view = self.me(raw)
        if view.account.state != "active" or permission not in view.account.permissions:
            raise AuthError(403, "forbidden")
        return view.account
