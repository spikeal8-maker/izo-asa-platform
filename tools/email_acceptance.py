"""Real PG/HTTP AUTH-002 proof races and restart. Synthetic fixtures only."""
import json
import os
import secrets
import sys
import time
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
import sqlalchemy as sa

from auth_acceptance import Client, check
from izo.config import Settings
from izo.accounts import repository as repo, tables as t
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.accounts.challenge_policy import ChallengeSettings
from izo.accounts.challenge_tables import challenges
from izo.accounts.security import token_hash
from izo.accounts.test_mail import messages


def proof(auth, policy, account, kind):
    return next(m["token"] for m in messages(auth, policy, UUID(account)) if m["kind"] == kind)


def joined_credential_snapshot(auth, account_id):
    """Wait for a real PostgreSQL lock, not a guessed sleep-based race."""
    worker_pid = Queue()
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with auth.engine.begin() as writer:
            old = repo.account_by_id(writer, UUID(account_id), lock=True)["password_hash"]
            def reader():
                with auth.engine.begin() as conn:
                    worker_pid.put(conn.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    return repo.account_by_id(conn, UUID(account_id), lock=True)["password_hash"]
            future = pool.submit(reader)
            pid = worker_pid.get(timeout=5)
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                writer.execute(sa.text("SELECT pg_stat_clear_snapshot()"))
                waiting = writer.execute(sa.text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                                         {"pid": pid}).scalar_one_or_none() == "Lock"
                if waiting:
                    break
                time.sleep(0.02)
            check(waiting, "credential_reader_actually_waited")
            identity = writer.execute(sa.select(t.identities.c.id).where(
                t.identities.c.account_id == UUID(account_id), t.identities.c.provider == "email")).scalar_one()
            writer.execute(sa.update(t.passwords).where(t.passwords.c.identity_id == identity)
                           .values(password_hash="isolated-snapshot-canary"))
        check(future.result(timeout=5) == "isolated-snapshot-canary", "fresh_joined_credentials_after_lock")
        with auth.engine.begin() as conn:
            conn.execute(sa.update(t.passwords).where(t.passwords.c.identity_id == identity).values(password_hash=old))
    finally:
        pool.shutdown(wait=True)


def before(auth, policy):
    email = f"proof-ci-{uuid4().hex}@example.invalid"
    invitation = auth.issue_invite()
    pwd, replacement, final = (secrets.token_urlsafe(28) for _ in range(3))
    client = Client(auth.policy.cookie_name)
    status, output = client.call("POST", "/register", {
        "email": email, "password": pwd, "display_name": "Proof CI", "invite_code": invitation})
    check(status == 201, "proof_register")
    account, old_cookie = output["account"]["id"], client.raw
    joined_credential_snapshot(auth, account)
    check(client.call("POST", "/email/verification/request")[0] == 202, "proof_request")
    value = proof(auth, policy, account, "verify_email")
    check(client.call("POST", "/email/verification/confirm", {"token": value},
                      headers={"X-CSRF-Token": "invalid"})[0] == 403, "proof_csrf")

    def confirm(_):
        worker = Client(client.name, client.raw)
        worker.csrf = client.csrf
        return worker.call("POST", "/email/verification/confirm", {"token": value})[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        check(sorted(pool.map(confirm, range(2))) == [204, 400], "proof_single_use_race")
    status, verified = client.call("GET", "/me")
    check(status == 200 and verified["account"]["email_verified"], "verified_in_pg")
    public = Client(client.name)
    check(public.call("POST", "/password/forgot", {"email": email})[0] == 202, "reset_request")
    reset = proof(auth, policy, account, "reset_password")

    def consume(_):
        return Client(client.name).call("POST", "/password/reset", {
            "token": reset, "password": replacement, "confirmation": replacement})[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        check(sorted(pool.map(consume, range(2))) == [204, 400], "reset_single_use_race")
    check(Client(client.name, old_cookie).call("GET", "/me")[0] == 401, "reset_revokes_cookie")
    check(client.call("POST", "/login", {"email": email, "password": replacement})[0] == 200, "new_password_login")
    active_cookie = client.raw
    check(public.call("POST", "/password/forgot", {"email": email})[0] == 202, "pending_reset")
    pending = proof(auth, policy, account, "reset_password")
    with auth.engine.begin() as conn:
        invite_id = str(conn.execute(sa.select(t.invites.c.id).where(
            t.invites.c.token_hash == token_hash(invitation))).scalar_one())
        stored = conn.execute(sa.select(challenges).where(challenges.c.id == UUID(pending[:32]))).mappings().one()
        check(stored["token_hash"] == token_hash(pending) and pending not in str(stored), "hashed_proof_pg")
    print("EMAIL_BEFORE_OK: verification/reset single-use PG races, revocation, secret-free proof storage", file=sys.stderr)
    # Only synthetic private fixture stdout, never print this file into a log/artifact.
    print(json.dumps({"schema": 1, "account": account, "email": email, "invitation": invite_id,
        "cookie_name": client.name, "active_cookie": active_cookie, "revoked_cookie": old_cookie,
        "consumed": reset, "pending": pending, "final_password": final}))


def after(auth, policy):
    item = json.loads(sys.stdin.read(16384))
    check(item["schema"] == 1 and item["email"].startswith("proof-ci-")
          and item["email"].endswith("@example.invalid"), "proof_fixture_scope")
    client = Client(item["cookie_name"], item["active_cookie"])
    status, output = client.call("GET", "/me")
    check(status == 200 and output["account"]["id"] == item["account"]
          and output["account"]["email_verified"], "verification_survives_restart")
    check(Client(client.name, item["revoked_cookie"]).call("GET", "/me")[0] == 401, "revocation_survives_restart")
    check(proof(auth, policy, item["account"], "reset_password") == item["pending"], "pending_mail_survives_restart")
    data = {"token": item["consumed"], "password": item["final_password"], "confirmation": item["final_password"]}
    check(client.call("POST", "/password/reset", data)[0] == 400, "used_proof_stays_used")
    data["token"] = item["pending"]
    check(client.call("POST", "/password/reset", data)[0] == 204, "pending_proof_works_after_restart")
    check(Client(client.name, item["active_cookie"]).call("GET", "/me")[0] == 401, "new_reset_revokes_previous_session")
    check(client.call("POST", "/login", {"email": item["email"], "password": item["final_password"]})[0] == 200,
          "final_login")
    with auth.engine.begin() as conn:
        account = repo.account_by_id(conn, UUID(item["account"]), lock=True)
        check(account["email"] == item["email"], "exact_cleanup_scope")
        conn.execute(sa.delete(t.audit).where(t.audit.c.account_id == account["id"]))
        conn.execute(sa.delete(t.accounts).where(t.accounts.c.id == account["id"]))
        conn.execute(sa.delete(t.invites).where(t.invites.c.id == UUID(item["invitation"])))
    print("EMAIL_AFTER_OK: verified identity, consumed/pending proofs, password and sessions after Compose down/up")


def main():
    config = Settings()
    if (config.environment != "test" or config.pg_host != "postgres" or config.pg_database != "izo"
            or os.environ.get("IZO_AUTH_ACCEPTANCE") != "isolated"):
        raise SystemExit("Refusing email acceptance outside isolated test stack")
    engine = repo.create_auth_engine(config)
    auth, policy = AuthService(engine, AuthSettings()), ChallengeSettings()
    try:
        policy.require_enabled()
        phase = sys.argv[1] if len(sys.argv) == 2 else ""
        if phase == "before":
            before(auth, policy)
        elif phase == "after":
            after(auth, policy)
        else:
            raise ValueError("Expected before or after")
    except Exception as exc:
        print("EMAIL_ACCEPTANCE_FAILED: " + type(exc).__name__, file=sys.stderr)
        if isinstance(exc, AssertionError):
            print(str(exc), file=sys.stderr)  # Only fixed check labels.
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
