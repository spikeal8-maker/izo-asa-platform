"""Real PostgreSQL + HTTP acceptance, only on the explicitly opted-in CI stack.

Before phase writes ephemeral test cookies to redirected stdout (NOT an artifact).
After phase reads them from stdin following actual Compose down/up and deletes fixtures.
"""
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import sqlalchemy as sa

from izo.config import Settings
from izo.accounts import tables as t, repository as repo
from izo.accounts.schemas import LoginInput
from izo.accounts.security import AuthError, token_hash
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings

BASE = "http://api:8000/api/v1/auth"
ORIGIN = "http://localhost:8080"


class Client:
    def __init__(self, cookie_name, raw=""):
        self.name, self.raw, self.csrf = cookie_name, raw, ""

    def call(self, method, path, data=None, headers=None):
        sent = {"Origin": ORIGIN, "X-IZO-Request": "web", "Content-Type": "application/json"}
        if self.raw:
            sent["Cookie"] = f"{self.name}={self.raw}"
        if self.csrf:
            sent["X-CSRF-Token"] = self.csrf
        sent.update(headers or {})
        body = json.dumps(data if data is not None else {}).encode() if method != "GET" else None
        request = Request(BASE + path, data=body, headers=sent, method=method)
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(65536)
            decoded = json.loads(raw) if raw else None
            cookie = SimpleCookie(response.headers.get("Set-Cookie", ""))
            if self.name in cookie:
                self.raw = cookie[self.name].value
            if response.status < 300 and isinstance(decoded, dict) and "csrf_token" in decoded:
                self.csrf = decoded["csrf_token"]
            return response.status, decoded


def check(condition, name):
    if not condition:
        raise AssertionError(name)  # Never include credentials/raw responses.


def before(engine, service):
    accounts, invite_ids = [], []
    cookie = service.policy.cookie_name

    def data(email=None, invitation=None):
        code = invitation or service.issue_invite()
        with engine.begin() as conn:
            invite_ids.append(str(conn.execute(sa.select(t.invites.c.id).where(
                t.invites.c.token_hash == token_hash(code))).scalar_one()))
        return {"email": email or f"auth-ci-{uuid4().hex}@example.invalid",
                "password": secrets.token_urlsafe(28), "display_name": "Auth CI",
                "invite_code": code}

    alice, bob = Client(cookie), Client(cookie)
    a_data, b_data = data(), data()
    for client, payload in [(alice, a_data), (bob, b_data)]:
        status, output = client.call("POST", "/register", payload)
        check(status == 201, "register")
        check(output["account"]["permissions"] == [] and output["account"]["email_verified"] is False,
              "no_staff_no_fake_verification")
        check(client.raw not in json.dumps(output) and payload["password"] not in json.dumps(output), "secret_response")
        accounts.append(output["account"]["id"])
    old_cookie = alice.raw
    status, listed = alice.call("GET", "/sessions")
    old_session = listed["sessions"][0]["id"]
    check(status == 200, "sessions")
    check(bob.call("DELETE", "/sessions/" + old_session)[0] == 404, "foreign_session")
    check(Client(cookie, "A" * 43).call("GET", "/me")[0] == 401, "forged_cookie")
    check(alice.call("POST", "/logout", headers={"X-CSRF-Token": "wrong"})[0] == 403, "csrf")
    check(alice.call("POST", "/logout", headers={"Origin": "https://evil.invalid"})[0] == 403, "origin")
    status, output = alice.call("POST", "/login", {k: a_data[k] for k in ("email", "password")})
    check(status == 200 and alice.raw != old_cookie, "new_bearer")
    check(alice.call("DELETE", "/sessions/" + old_session)[0] == 204, "revoke_old")
    check(Client(cookie, old_cookie).call("GET", "/me")[0] == 401, "revoked_replay")

    # Actual PostgreSQL uniqueness/row locks, through two concurrent HTTP requests.
    common = data()
    variants = [common, {**common, "email": f"auth-ci-{uuid4().hex}@example.invalid"}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda payload: Client(cookie).call("POST", "/register", payload), variants))
    check(sorted(status for status, _ in results) == [201, 400], "one_invite_race")
    accounts.extend(output["account"]["id"] for status, output in results if status == 201)
    common_email = f"auth-ci-{uuid4().hex}@example.invalid"
    variants = [data(common_email), data(common_email)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda payload: Client(cookie).call("POST", "/register", payload), variants))
    check(sorted(status for status, _ in results) == [201, 400], "one_identity_race")
    accounts.extend(output["account"]["id"] for status, output in results if status == 201)

    # DB-backed limiter uses one atomic upsert per counter even on concurrent workers.
    rate_id, window = "f" + uuid4().hex + "0" * 31, service.now()
    def counter(_):
        with engine.begin() as conn:
            return repo.consume_rate(conn, rate_id, window, 5)
    with ThreadPoolExecutor(max_workers=6) as pool:
        counts = list(pool.map(counter, range(12)))
    check(sum(count <= 5 for count in counts) == 5, "atomic_rate_limit")

    # Login session cap is serialized by the PostgreSQL account row lock.
    cap_data = data()
    cap_client = Client(cookie)
    status, output = cap_client.call("POST", "/register", cap_data)
    check(status == 201, "cap_account")
    accounts.append(output["account"]["id"])
    capped = AuthService(engine, service.policy.model_copy(update={"max_sessions": 2}), service.clock)
    def login(_):
        try:
            capped.login(LoginInput(email=cap_data["email"], password=cap_data["password"]), "cap-test", "CI")
            return 200
        except AuthError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        check(sorted(pool.map(login, range(2))) == [200, 409], "session_cap_race")

    with engine.begin() as conn:
        row = conn.execute(sa.select(t.sessions).where(t.sessions.c.token_hash == token_hash(alice.raw))).mappings().one()
        check(row["token_hash"] != alice.raw, "hashed_bearer_in_database")
        stored = conn.execute(sa.select(t.passwords.c.password_hash).join(t.identities,
            t.identities.c.id == t.passwords.c.identity_id).where(t.identities.c.account_id == UUID(accounts[0]))).scalar_one()
        check(stored.startswith("scrypt-v1$") and stored != a_data["password"], "hashed_password")
    print("AUTH_BEFORE_OK: HTTP, PostgreSQL races, revocation, scopes and hashing", file=sys.stderr)
    # Only test-generated cookies in a private RUNNER_TEMP file, never credentials of real users.
    print(json.dumps({"schema": 1, "cookie": cookie, "active": alice.raw, "revoked": old_cookie,
                      "account": accounts[0], "accounts": accounts, "invites": invite_ids,
                      "rate_id": rate_id}))


def after(engine):
    fixture = json.loads(sys.stdin.read(16384))
    check(fixture["schema"] == 1, "fixture_version")
    client = Client(fixture["cookie"], fixture["active"])
    status, output = client.call("GET", "/me")
    check(status == 200 and output["account"]["id"] == fixture["account"], "session_survives_real_restart")
    check(Client(fixture["cookie"], fixture["revoked"]).call("GET", "/me")[0] == 401, "revocation_survives_restart")
    check(client.call("POST", "/sessions/revoke-others")[0] == 204, "revoke_others")
    check(client.call("POST", "/logout")[0] == 204, "logout_after_restart")
    ids = [UUID(x) for x in fixture["accounts"]]
    with engine.begin() as conn:
        subjects = list(conn.execute(sa.select(t.identities.c.subject).where(t.identities.c.account_id.in_(ids))).scalars())
        check(subjects and all(x.startswith("auth-ci-") and x.endswith("@example.invalid") for x in subjects), "fixture_cleanup_scope")
        conn.execute(sa.delete(t.audit).where(t.audit.c.account_id.in_(ids)))
        conn.execute(sa.delete(t.accounts).where(t.accounts.c.id.in_(ids)))
        conn.execute(sa.delete(t.invites).where(t.invites.c.id.in_([UUID(x) for x in fixture["invites"]])))
        conn.execute(sa.delete(t.limits).where(t.limits.c.bucket_key == fixture["rate_id"]))
    print("AUTH_AFTER_OK: account/session/revocation persisted across Compose down/up; test accounts removed")


def main():
    config = Settings()
    if (config.environment != "test" or config.pg_host != "postgres" or config.pg_database != "izo"
            or os.environ.get("IZO_AUTH_ACCEPTANCE") != "isolated"):
        raise SystemExit("Refusing acceptance outside opted-in isolated test stack")
    policy = AuthSettings()
    policy.require_configured()
    engine = repo.create_auth_engine(config)
    try:
        phase = sys.argv[1] if len(sys.argv) == 2 else ""
        if phase == "before":
            before(engine, AuthService(engine, policy))
        elif phase == "after":
            after(engine)
        else:
            raise ValueError("Expected before or after")
    except Exception as exc:
        print("AUTH_ACCEPTANCE_FAILED: " + type(exc).__name__, file=sys.stderr)
        # Assertion messages are fixed test labels, never response/credential values.
        if isinstance(exc, AssertionError):
            print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
