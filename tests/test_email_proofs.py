"""HTTP/service negative tests; SQLite here is NOT proof of PostgreSQL locking."""
from uuid import UUID, uuid4
import json
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool
from izo.app import create_app
from izo.config import Settings
from fastapi.testclient import TestClient
from pydantic import ValidationError
from izo.accounts import tables as t
from izo.accounts.routes import attach_accounts
from izo.accounts.settings import AuthSettings
from izo.accounts.service import AuthService
from izo.accounts.challenge_policy import ChallengeSettings, selector
from izo.accounts.challenge_schema import ResetInput
from izo.accounts.challenges import ChallengeService
from izo.accounts.challenge_tables import challenges, mail
from izo.accounts.security import AuthError, token_hash, verify_password
from izo.accounts.test_mail import messages

ORIGIN = "http://localhost:8080"
HEADERS = {"origin": ORIGIN, "x-izo-request": "web"}
PWD = "local test old password 2026"
NEW = "local test new password 2026"


@pytest.fixture
def ctx():
    engine = sa.create_engine("sqlite+pysqlite://", poolclass=StaticPool,
                             connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    t.metadata.create_all(engine)
    clock = [1800000000]
    auth = AuthService(engine, AuthSettings(registration="invite", rate_secret="test-rate-" * 5),
                       clock=lambda: clock[0])
    policy = ChallengeSettings(delivery="test", secret="test-proof-secret-" * 4)
    app = create_app(Settings(), readiness=lambda: True)
    app.state.accounts_service, app.state.challenge_settings = auth, policy
    with TestClient(app, base_url=ORIGIN) as client:
        yield auth, policy, client, clock
    engine.dispose()


def signup(ctx, email="email-proof@example.invalid"):
    auth, _, client, _ = ctx
    result = client.post("/api/v1/auth/register", headers=HEADERS, json={
        "email": email, "password": PWD, "display_name": "Email test", "invite_code": auth.issue_invite()})
    assert result.status_code == 201
    return result.json()


def post(ctx, path, data=None, csrf=None):
    return ctx[2].post("/api/v1/auth/" + path, headers={**HEADERS,
        **({"x-csrf-token": csrf} if csrf else {})}, json=data or {})


def latest(ctx, account, kind):
    result = messages(ctx[0], ctx[1], UUID(account["account"]["id"]))
    return next(m for m in result if m["kind"] == kind)


def verify(ctx, account):
    assert post(ctx, "email/verification/request", csrf=account["csrf_token"]).status_code == 202
    proof = latest(ctx, account, "verify_email")["token"]
    assert post(ctx, "email/verification/confirm", {"token": proof}, account["csrf_token"]).status_code == 204
    return proof


def reset_request(ctx, account):
    assert post(ctx, "password/forgot", {"email": account["account"]["email"]}).status_code == 202
    return latest(ctx, account, "reset_password")["token"]


def test_verified_identity_is_real_and_proof_one_use(ctx):
    account = signup(ctx)
    token = verify(ctx, account)
    assert ctx[2].get("/api/v1/auth/me").json()["account"]["email_verified"] is True
    assert post(ctx, "email/verification/confirm", {"token": token}, account["csrf_token"]).status_code == 400
    with ctx[0].engine.begin() as conn:
        assert conn.execute(sa.select(t.identities.c.verified_at)).scalar_one() == ctx[3][0]
        rows = conn.execute(sa.select(challenges)).mappings().all()
        assert all(token != r["token_hash"] for r in rows)
        assert token not in str(rows) and token not in str(conn.execute(sa.select(mail)).all())


def test_reset_revokes_all_sessions_and_does_not_login(ctx):
    account = signup(ctx)
    verify(ctx, account)
    old_cookie = ctx[2].cookies[ctx[0].policy.cookie_name]
    assert post(ctx, "login", {"email": account["account"]["email"], "password": PWD}).status_code == 200
    second_cookie = ctx[2].cookies[ctx[0].policy.cookie_name]
    token = reset_request(ctx, account)
    # A later request must not let an unauthenticated caller invalidate the earlier link.
    reset_request(ctx, account)
    result = post(ctx, "password/reset", {"token": token, "password": NEW, "confirmation": NEW})
    assert result.status_code == 204
    for cookie in (old_cookie, second_cookie):
        with pytest.raises(AuthError, match="auth_required"):
            ctx[0].me(cookie)
    assert ctx[2].get("/api/v1/auth/me").status_code == 401
    assert post(ctx, "login", {"email": account["account"]["email"], "password": PWD}).status_code == 401
    assert post(ctx, "login", {"email": account["account"]["email"], "password": NEW}).status_code == 200
    assert post(ctx, "password/reset", {"token": token, "password": PWD, "confirmation": PWD}).status_code == 400
    assert latest(ctx, account, "password_changed")["text"]


@pytest.mark.parametrize("state", ["active", "security_locked", "deletion_pending", "deleted"])
def test_reset_request_does_not_disclose_existence_or_restriction(ctx, state):
    account = signup(ctx)
    verify(ctx, account)
    with ctx[0].engine.begin() as conn:
        conn.execute(sa.update(t.accounts).values(state=state))
    known = post(ctx, "password/forgot", {"email": account["account"]["email"]})
    unknown = post(ctx, "password/forgot", {"email": "absent@example.invalid"})
    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content == b'{"accepted":true,"delivery":"test"}'
    with ctx[0].engine.begin() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(challenges).where(
            challenges.c.purpose == "reset_password", challenges.c.account_id.is_not(None))).scalar_one()
        assert count == (1 if state == "active" else 0)


def test_unverified_email_cannot_reset_password(ctx):
    account = signup(ctx)
    result = post(ctx, "password/forgot", {"email": account["account"]["email"]})
    assert result.status_code == 202
    assert messages(ctx[0], ctx[1], UUID(account["account"]["id"])) == []
    assert ctx[2].get("/api/v1/auth/me").json()["account"]["email_verified"] is False


def test_wrong_account_cannot_confirm_or_burn_someone_elses_token(ctx):
    a = signup(ctx)
    post(ctx, "email/verification/request", csrf=a["csrf_token"])
    proof = latest(ctx, a, "verify_email")["token"]
    a_cookie = ctx[2].cookies[ctx[0].policy.cookie_name]
    ctx[2].cookies.clear()
    b = signup(ctx, "second@example.invalid")
    assert post(ctx, "email/verification/confirm", {"token": proof}, b["csrf_token"]).status_code == 400
    with ctx[0].engine.begin() as conn:
        assert conn.execute(sa.select(challenges.c.attempts)).scalar_one() == 0
    ctx[2].cookies.clear()
    ctx[2].cookies.set(ctx[0].policy.cookie_name, a_cookie)
    assert post(ctx, "email/verification/confirm", {"token": proof}, a["csrf_token"]).status_code == 204


def test_failed_attempts_commit_and_lock_proof(ctx):
    a = signup(ctx)
    post(ctx, "email/verification/request", csrf=a["csrf_token"])
    proof = latest(ctx, a, "verify_email")["token"]
    bad = proof[:33] + "A" * 43
    for _ in range(5):
        assert post(ctx, "email/verification/confirm", {"token": bad}, a["csrf_token"]).status_code == 400
    assert post(ctx, "email/verification/confirm", {"token": proof}, a["csrf_token"]).status_code == 400
    with ctx[0].engine.begin() as conn:
        assert conn.execute(sa.select(challenges.c.attempts)).scalar_one() == 5


@pytest.mark.parametrize("advance", [600, 601])
def test_proof_expiry_is_strict(ctx, advance):
    a = signup(ctx)
    post(ctx, "email/verification/request", csrf=a["csrf_token"])
    proof = latest(ctx, a, "verify_email")["token"]
    ctx[3][0] += advance
    assert post(ctx, "email/verification/confirm", {"token": proof}, a["csrf_token"]).status_code == 400
    assert ctx[2].get("/api/v1/auth/me").json()["account"]["email_verified"] is False


def test_purpose_rotation_and_password_binding(ctx):
    a = signup(ctx)
    post(ctx, "email/verification/request", csrf=a["csrf_token"])
    proof = latest(ctx, a, "verify_email")["token"]
    assert post(ctx, "password/reset", {"token": proof, "password": NEW, "confirmation": NEW}).status_code == 400
    rotated = ChallengeSettings(delivery="test", secret="rotated-" * 8)
    assert messages(ctx[0], rotated, UUID(a["account"]["id"])) == []
    ctx[2].app.state.challenge_settings = rotated
    assert post(ctx, "email/verification/confirm", {"token": proof}, a["csrf_token"]).status_code == 400


def test_change_password_requires_current_password_and_cancels_reset(ctx):
    a = signup(ctx)
    verify(ctx, a)
    proof = reset_request(ctx, a)
    body = {"current_password": "wrong", "password": NEW, "confirmation": NEW}
    assert post(ctx, "password/change", body, a["csrf_token"]).status_code == 403
    body["current_password"] = PWD
    assert post(ctx, "password/change", body).status_code == 403
    assert post(ctx, "password/change", body, a["csrf_token"]).status_code == 204
    assert post(ctx, "password/reset", {"token": proof, "password": PWD, "confirmation": PWD}).status_code == 400
    assert ctx[2].get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("path,payload", [
    ("email/verification/request", {}), ("email/verification/confirm", {"token": "a" * 32 + "." + "A" * 43}),
    ("password/forgot", {"email": "a@example.invalid"}),
    ("password/reset", {"token": "a" * 32 + "." + "A" * 43, "password": NEW, "confirmation": NEW}),
    ("password/change", {"current_password": PWD, "password": NEW, "confirmation": NEW})])
def test_all_new_mutations_enforce_origin(ctx, path, payload):
    result = ctx[2].post("/api/v1/auth/" + path, json=payload, headers={**HEADERS, "origin": "https://evil.invalid"})
    assert result.status_code == 403


@pytest.mark.parametrize("payload", [
    {"token": "secret", "password": NEW, "confirmation": NEW},
    {"token": "a" * 32 + "." + "A" * 43, "password": NEW, "confirmation": "mismatched long password"},
    {"token": "a" * 32 + "." + "A" * 43, "password": NEW, "confirmation": NEW, "role": "owner"},
])
def test_invalid_inputs_redacted(ctx, payload):
    result = post(ctx, "password/reset", payload)
    assert result.status_code == 422
    assert result.json() == {"error": {"code": "invalid_input"}}
    assert NEW not in result.text


def test_limiter_is_independent_and_forgot_does_not_revoke_sessions(ctx):
    a = signup(ctx)
    verify(ctx, a)
    for _ in range(3):
        assert post(ctx, "password/forgot", {"email": a["account"]["email"]}).status_code == 202
    assert post(ctx, "password/forgot", {"email": a["account"]["email"]}).status_code == 429
    assert ctx[2].get("/api/v1/auth/me").status_code == 200
    assert post(ctx, "login", {"email": a["account"]["email"], "password": PWD}).status_code == 200


def test_test_mail_has_no_public_endpoint(ctx):
    for path in ("/api/v1/auth/test-mail", "/api/v1/auth/challenges", "/api/test-mail"):
        assert ctx[2].get(path).status_code == 404


def test_disabled_delivery_does_not_silently_send_or_create_proofs(ctx):
    ctx[2].app.state.challenge_settings = ChallengeSettings()
    assert post(ctx, "password/forgot", {"email": "a@example.invalid"}).status_code == 503
    with ctx[0].engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(challenges)).scalar_one() == 0


def test_reset_and_verify_cannot_remove_security_lock(ctx):
    a = signup(ctx)
    verify(ctx, a)
    proof = reset_request(ctx, a)
    with ctx[0].engine.begin() as conn:
        conn.execute(sa.update(t.accounts).values(state="security_locked"))
    assert post(ctx, "password/reset", {"token": proof, "password": NEW, "confirmation": NEW}).status_code == 400
    with ctx[0].engine.begin() as conn:
        assert conn.execute(sa.select(t.accounts.c.state)).scalar_one() == "security_locked"
        assert verify_password(PWD, conn.execute(sa.select(t.passwords.c.password_hash)).scalar_one())


def test_reset_rolls_back_password_sessions_and_proof_on_audit_failure(ctx, monkeypatch):
    from izo.accounts import repository
    a = signup(ctx)
    verify(ctx, a)
    proof = reset_request(ctx, a)
    raw = ctx[2].cookies[ctx[0].policy.cookie_name]
    original = repository.event
    def fail(conn, account, action, *args):
        if action == "password.reset":
            raise RuntimeError("synthetic audit failure")
        return original(conn, account, action, *args)
    monkeypatch.setattr(repository, "event", fail)
    service = ChallengeService(ctx[0], ctx[1])
    with pytest.raises(RuntimeError, match="synthetic"):
        service.reset(ResetInput(token=proof, password=NEW, confirmation=NEW), "rollback-test")
    assert ctx[0].me(raw).account.id == UUID(a["account"]["id"])
    with ctx[0].engine.begin() as conn:
        assert verify_password(PWD, conn.execute(sa.select(t.passwords.c.password_hash)).scalar_one())
        row = conn.execute(sa.select(challenges).where(challenges.c.id == selector(proof))).mappings().one()
        assert row["consumed_at"] is None and row["cancelled_at"] is None


@pytest.mark.parametrize("value", ["bad", "a" * 32 + "." + "Ж" * 43, "../" + "a" * 73])
def test_proof_selector_never_becomes_sql_or_filename(value):
    with pytest.raises(AuthError, match="invalid_challenge"):
        selector(value)
