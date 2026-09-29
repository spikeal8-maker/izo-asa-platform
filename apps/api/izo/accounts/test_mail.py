"""Operator-only TEST mailbox: no HTTP endpoint, no SMTP, no provider credentials.

Metadata persists; one-use links are rendered using a separate configured secret.
The operator must explicitly request sensitive test output. Never attach it to PRs.
"""
import argparse
import json
import os
import sys
from uuid import UUID
import hmac
import sqlalchemy as sa

from . import tables as t, repository as repo
from .challenge_tables import challenges, mail
from .challenge_policy import ChallengeSettings, binding
from .security import token_hash
from .service import AuthService
from .settings import AuthSettings


def messages(auth, policy, account_id: UUID) -> list[dict]:
    """Trusted operator/test boundary, NEVER call from a public route."""
    policy.require_enabled()
    output = []
    with auth.engine.begin() as conn:
        account = repo.account_by_id(conn, account_id, lock=True)
        if not account:
            return output
        rows = conn.execute(sa.select(mail).where(mail.c.account_id == account_id)
                            .order_by(mail.c.created_at.desc(), mail.c.id).limit(20)).mappings().all()
        for message in rows:
            if message["kind"] == "password_changed":
                output.append({"kind": message["kind"], "to": account["email"],
                               "text": "Пароль изменён. Войдите заново; старые сессии отозваны."})
                continue
            row = conn.execute(sa.select(challenges).where(
                challenges.c.id == message["challenge_id"])).mappings().first()
            if (not row or row["expires_at"] <= auth.now() or row["consumed_at"] is not None
                    or row["cancelled_at"] is not None or row["attempts"] >= policy.max_attempts
                    or row["binding_hash"] != binding(account)
                    or account["state"] not in {"active", "generation_suspended"}):
                continue
            value = policy.proof(row["id"], row["purpose"])
            if not hmac.compare_digest(token_hash(value), row["token_hash"]):
                continue  # Rotation invalidates outstanding links, never falls back.
            path = "/verify-email" if row["purpose"] == "verify_email" else "/password/reset"
            output.append({"kind": message["kind"], "to": account["email"], "token": value,
                "url": auth.policy.origins[0] + path + "#token=" + value,
                "expires_at": row["expires_at"]})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", type=UUID, required=True)
    parser.add_argument("--show-sensitive", action="store_true")
    args = parser.parse_args()
    # Refuse output before any database query; dev/test only and deliberate opt-in.
    if not args.show_sensitive or os.environ.get("IZO_ENVIRONMENT", "development") not in {"development", "test"}:
        raise SystemExit("Test-mail inspection requires dev/test and --show-sensitive")
    from izo.config import Settings
    policy = ChallengeSettings()
    engine = None
    try:
        policy.require_enabled()
        engine = repo.create_auth_engine(Settings())
        auth = AuthService(engine, AuthSettings())
        print(json.dumps(messages(auth, policy, args.account), ensure_ascii=False, indent=2))
    except Exception as exc:
        print("TEST_MAIL_UNAVAILABLE: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
