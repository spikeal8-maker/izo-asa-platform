"""Email verification/recovery on the existing accounts, not another identity system."""
import hmac
from uuid import uuid4
import sqlalchemy as sa

from . import repository as repo, tables as t
from .challenge_tables import challenges, mail
from .challenge_policy import ChallengeSettings, binding, selector
from .security import AuthError, rate_key, token_hash, hash_password, verify_password
from .service import AuthService

ALLOWED_STATES = {"active", "generation_suspended"}


class ChallengeService:
    def __init__(self, auth: AuthService, policy: ChallengeSettings):
        self.auth, self.policy = auth, policy

    def throttle(self, namespace, subject, peer, limit=None):
        self.policy.require_enabled()
        self.auth.policy.require_configured()
        now, window = self.auth.now(), self.auth.policy.rate_window
        start = now - now % window
        secret = self.auth.policy.rate_secret.get_secret_value()
        maximum = limit or self.policy.request_limit
        with self.auth.engine.begin() as conn:
            network = repo.consume_rate(conn, rate_key(secret, "recovery:network", peer),
                                        start, self.auth.policy.network_limit)
            count = repo.consume_rate(conn, rate_key(secret, "recovery:" + namespace, subject),
                                      start, maximum)
        if network > self.auth.policy.network_limit or count > maximum:
            raise AuthError(429, "rate_limited", start + window - now)

    def _issue(self, conn, account, purpose):
        now, identity = self.auth.now(), None
        if account:
            identity = conn.execute(sa.select(t.identities).where(
                t.identities.c.account_id == account["id"], t.identities.c.provider == "email"
            )).mappings().first()
        challenge_id = uuid4()
        conn.execute(sa.insert(challenges).values(id=challenge_id,
            account_id=account["id"] if identity else None, identity_id=identity["id"] if identity else None,
            purpose=purpose, token_hash=token_hash(self.policy.proof(challenge_id, purpose)),
            binding_hash=binding(account) if identity else None, created_at=now,
            expires_at=now + self.policy.ttl_seconds))
        conn.execute(sa.insert(mail).values(id=uuid4(), challenge_id=challenge_id,
            account_id=account["id"] if identity else None, identity_id=identity["id"] if identity else None,
            kind=purpose, created_at=now))
        repo.event(conn, account["id"] if identity else None, "email.proof_requested", now)
        # Do not return proof/selector/eligibility to the HTTP caller. New reset
        # requests do not cancel existing ones: avoids unauthenticated denial of recovery.

    def request_verification(self, bearer, csrf, peer):
        view = self.auth.me(bearer)
        self.throttle("verification", str(view.account.id), peer)
        with self.auth.engine.begin() as conn:
            account, _ = self.auth._session(conn, bearer, csrf, mutation=True)
            if account["state"] not in ALLOWED_STATES:
                raise AuthError(403, "account_restricted")
            if account["verified_at"] is None:
                self._issue(conn, account, "verify_email")

    def request_reset(self, email, peer):
        self.throttle("reset", email, peer)
        with self.auth.engine.begin() as conn:
            candidate = repo.account_by_email(conn, email)
            account = repo.account_by_id(conn, candidate["id"], lock=True) if candidate else None
            eligible = (account and account["state"] in ALLOWED_STATES
                        and account["email"] == email and account["verified_at"] is not None
                        and account["password_hash"])
            # Same response and insert shape for unknown/unverified/restricted
            # addresses. No recipient is stored for dummy intents. Not a claim
            # of constant-time DB execution or complete enumeration resistance.
            self._issue(conn, account if eligible else None, "reset_password")

    def _locked_proof(self, conn, value, purpose, owner=None):
        challenge_id = selector(value)
        initial = conn.execute(sa.select(challenges).where(challenges.c.id == challenge_id)).mappings().first()
        if not initial or (owner and initial["account_id"] != owner["id"]):
            return None
        # Universal lock order: account -> session (when required) -> challenge.
        account = owner or (repo.account_by_id(conn, initial["account_id"], lock=True)
                            if initial["account_id"] else None)
        row = conn.execute(sa.select(challenges).where(challenges.c.id == challenge_id)
                           .with_for_update()).mappings().first()
        if (not account or not row or row["purpose"] != purpose
                or account["state"] not in ALLOWED_STATES or row["expires_at"] <= self.auth.now()
                or row["consumed_at"] is not None or row["cancelled_at"] is not None
                or row["attempts"] >= self.policy.max_attempts
                or row["binding_hash"] != binding(account)):
            return None
        if (not hmac.compare_digest(token_hash(value), row["token_hash"])
                or not hmac.compare_digest(value, self.policy.proof(challenge_id, purpose))):
            conn.execute(sa.update(challenges).where(challenges.c.id == challenge_id)
                         .values(attempts=row["attempts"] + 1))
            repo.event(conn, account["id"], "email.proof_rejected", self.auth.now(), challenge_id)
            return None  # Caller raises only AFTER transaction commits attempts.
        return account, row

    def confirm(self, bearer, csrf, value, peer):
        view = self.auth.me(bearer)
        self.throttle("confirm", str(view.account.id), peer, 10)
        success = False
        with self.auth.engine.begin() as conn:
            owner, _ = self.auth._session(conn, bearer, csrf, mutation=True)
            result = self._locked_proof(conn, value, "verify_email", owner)
            if result:
                account, proof = result
                now = self.auth.now()
                conn.execute(sa.update(t.identities).where(t.identities.c.id == proof["identity_id"])
                             .values(verified_at=now))
                self._invalidate(conn, account["id"], now, "verify_email")
                conn.execute(sa.update(challenges).where(challenges.c.id == proof["id"])
                             .values(consumed_at=now))
                repo.event(conn, account["id"], "email.verified", now, proof["id"])
                success = True
        if not success:
            raise AuthError(400, "invalid_challenge")

    def _invalidate(self, conn, account_id, now, purpose=None):
        query = sa.update(challenges).where(challenges.c.account_id == account_id,
                                            challenges.c.cancelled_at.is_(None))
        if purpose:
            query = query.where(challenges.c.purpose == purpose)
        conn.execute(query.values(cancelled_at=now))

    def _replace_password(self, conn, account, encoded, now, action):
        identity_id = conn.execute(sa.select(t.identities.c.id).where(
            t.identities.c.account_id == account["id"], t.identities.c.provider == "email")).scalar_one()
        changed = conn.execute(sa.update(t.passwords).where(t.passwords.c.identity_id == identity_id)
                               .values(password_hash=encoded))
        if changed.rowcount != 1:
            raise AuthError(400, "invalid_challenge")
        conn.execute(sa.update(t.sessions).where(t.sessions.c.account_id == account["id"],
                     t.sessions.c.revoked_at.is_(None)).values(revoked_at=now))
        self._invalidate(conn, account["id"], now)
        # Confirmation intent contains no password or bearer. Delivery remains test-only.
        conn.execute(sa.insert(mail).values(id=uuid4(), account_id=account["id"],
            identity_id=identity_id, kind="password_changed", created_at=now))
        repo.event(conn, account["id"], action, now)

    def reset(self, data, peer):
        value = data.token.get_secret_value()
        self.throttle("consume", str(selector(value)), peer, 10)
        # Bounded KDF before locks; same workload for invalid and valid proof.
        encoded = hash_password(data.password.get_secret_value())
        success = False
        with self.auth.engine.begin() as conn:
            result = self._locked_proof(conn, value, "reset_password")
            if result and result[0]["verified_at"] is not None:
                account, proof = result
                now = self.auth.now()
                self._replace_password(conn, account, encoded, now, "password.reset")
                conn.execute(sa.update(challenges).where(challenges.c.id == proof["id"])
                             .values(consumed_at=now))
                success = True
        if not success:
            raise AuthError(400, "invalid_challenge")

    def change_password(self, bearer, csrf, data, peer):
        view = self.auth.me(bearer)
        self.throttle("change", str(view.account.id), peer)
        with self.auth.engine.begin() as conn:
            account, _ = self.auth._session(conn, bearer, csrf, mutation=True)
            snapshot = account["password_hash"]
        valid = verify_password(data.current_password.get_secret_value(), snapshot)
        if not valid:
            raise AuthError(403, "reauth_required")
        encoded = hash_password(data.password.get_secret_value())
        with self.auth.engine.begin() as conn:
            current, _ = self.auth._session(conn, bearer, csrf, mutation=True)
            if current["state"] not in ALLOWED_STATES or current["password_hash"] != snapshot:
                raise AuthError(403, "reauth_required")
            self._replace_password(conn, current, encoded, self.auth.now(), "password.changed")
