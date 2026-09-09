"""Fast auth tests on an isolated SQLite database, not evidence of PostgreSQL locks."""
from uuid import UUID

import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from pydantic import ValidationError

from izo.app import create_app
from izo.config import Settings
from izo.accounts import tables as t
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.accounts.schemas import RegisterInput, LoginInput
from izo.accounts.security import AuthError, token_hash, verify_password

ORIGIN = "http://localhost:8080"
HEADERS = {"origin": ORIGIN, "x-izo-request": "web"}
PASSWORD = "test-only strong password 2026"


@pytest.fixture
def context():
    engine = sa.create_engine("sqlite+pysqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    t.metadata.create_all(engine)  # Test only; runtime exclusively uses Alembic.
    clock = [1800000000]
    policy = AuthSettings(registration="invite", rate_secret="test-rate-key-" * 4)
    service = AuthService(engine, policy, clock=lambda: clock[0])
    app = create_app(Settings(), readiness=lambda: True)
    app.state.accounts_service = service
    with TestClient(app, base_url=ORIGIN) as client:
        yield service, client, clock
    engine.dispose()


def registration(service, email="alice@example.invalid", **extra):
    return {"email": email, "password": PASSWORD, "display_name": "Тестовый пользователь",
            "invite_code": service.issue_invite(), **extra}


def signup(service, client, email="alice@example.invalid"):
    result = client.post("/api/v1/auth/register", json=registration(service, email), headers=HEADERS)
    assert result.status_code == 201, result.text
    return result


def test_account_is_persistent_server_identity_and_hashed_secrets(context):
    service, client, _ = context
    result = signup(service, client)
    data = result.json()
    assert data["account"]["permissions"] == []
    assert data["account"]["email_verified"] is False
    raw = client.cookies[service.policy.cookie_name]
    assert "HttpOnly" in result.headers["set-cookie"] and "SameSite=lax" in result.headers["set-cookie"]
    assert raw not in result.text and PASSWORD not in result.text
    with service.engine.begin() as conn:
        stored = conn.execute(sa.select(t.passwords.c.password_hash)).scalar_one()
        stored_token = conn.execute(sa.select(t.sessions.c.token_hash)).scalar_one()
        assert stored_token == token_hash(raw) and stored_token != raw
        assert stored != PASSWORD and verify_password(PASSWORD, stored)
    restarted = AuthService(service.engine, service.policy, service.clock)
    assert restarted.me(raw).account.id == service.me(raw).account.id
    assert client.get("/api/v1/auth/me").json()["account"]["id"] == data["account"]["id"]


@pytest.mark.parametrize("field,value", [("role", "admin"), ("permissions", ["admin.access"]),
                                        ("balance", 9999), ("owner_id", "forged")])
def test_signup_does_not_accept_privileges(context, field, value):
    service, client, _ = context
    body = registration(service, **{field: value})
    result = client.post("/api/v1/auth/register", json=body, headers=HEADERS)
    assert result.status_code == 422
    assert PASSWORD not in result.text and body["invite_code"] not in result.text
    with service.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.accounts)).scalar_one() == 0


@pytest.mark.parametrize("changes", [{}, {"origin": "https://evil.invalid"},
    {"origin": ORIGIN + ".evil.invalid", "x-izo-request": "web"},
    {**HEADERS, "sec-fetch-site": "cross-site"}, {"origin": "null", "x-izo-request": "web"}])
def test_login_csrf_and_missing_origin_are_blocked(context, changes):
    service, client, _ = context
    result = client.post("/api/v1/auth/register", json=registration(service), headers=changes)
    assert result.status_code == 403


def test_csrf_logout_and_server_revocation(context):
    service, client, _ = context
    receipt = signup(service, client).json()
    raw = client.cookies[service.policy.cookie_name]
    for csrf in [None, "wrong", b"\xff" * 43]:
        headers = {**HEADERS, **({"x-csrf-token": csrf} if csrf else {})}
        assert client.post("/api/v1/auth/logout", json={}, headers=headers).status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200
    result = client.post("/api/v1/auth/logout", json={}, headers={**HEADERS, "x-csrf-token": receipt["csrf_token"]})
    assert result.status_code == 204
    client.cookies.set(service.policy.cookie_name, raw)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_owner_and_permissions_are_rechecked(context):
    service, client, _ = context
    a = signup(service, client).json()
    a_raw = client.cookies[service.policy.cookie_name]
    a_id = service.list_sessions(a_raw).sessions[0].id
    client.cookies.clear()
    b = signup(service, client, "bob@example.invalid").json()
    assert a["account"]["id"] != b["account"]["id"]
    denied = client.delete(f"/api/v1/auth/sessions/{a_id}", headers={**HEADERS,
        "content-type": "application/json", "x-csrf-token": b["csrf_token"]})
    assert denied.status_code == 404
    assert service.me(a_raw).account.id == UUID(a["account"]["id"])
    with pytest.raises(AuthError, match="forbidden"):
        service.require_permission(a_raw, "admin.access")
    with service.engine.begin() as conn:
        conn.execute(sa.insert(t.permissions).values(account_id=UUID(a["account"]["id"]),
                                                     permission="admin.access"))
    assert service.require_permission(a_raw, "admin.access")
    with service.engine.begin() as conn:
        conn.execute(sa.delete(t.permissions))
    with pytest.raises(AuthError, match="forbidden"):
        service.require_permission(a_raw, "admin.access")


@pytest.mark.parametrize("expiration", ["idle", "absolute", "revoked", "locked"])
def test_invalid_session_states(context, expiration):
    service, client, clock = context
    signup(service, client)
    with service.engine.begin() as conn:
        if expiration == "idle":
            clock[0] += service.policy.idle_seconds
        elif expiration == "absolute":
            clock[0] += 1
            conn.execute(sa.update(t.sessions).values(expires_at=clock[0]))
        elif expiration == "revoked":
            conn.execute(sa.update(t.sessions).values(revoked_at=clock[0]))
        else:
            conn.execute(sa.update(t.accounts).values(state="security_locked"))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invite_single_use_and_email_canonicalization(context):
    service, client, _ = context
    body = registration(service, " ALICE@EXAMPLE.INVALID ")
    assert client.post("/api/v1/auth/register", json=body, headers=HEADERS).status_code == 201
    body["email"] = "other@example.invalid"
    assert client.post("/api/v1/auth/register", json=body, headers=HEADERS).status_code == 400
    duplicate = registration(service)
    assert client.post("/api/v1/auth/register", json=duplicate, headers=HEADERS).status_code == 400
    duplicate["email"] = "other@example.invalid"
    assert client.post("/api/v1/auth/register", json=duplicate, headers=HEADERS).status_code == 201


def test_login_rotates_bearer_and_revoke_others(context):
    service, client, _ = context
    signup(service, client)
    old = client.cookies[service.policy.cookie_name]
    result = client.post("/api/v1/auth/login", json={"email": "alice@example.invalid", "password": PASSWORD}, headers=HEADERS)
    assert result.status_code == 200 and client.cookies[service.policy.cookie_name] != old
    assert len(client.get("/api/v1/auth/sessions").json()["sessions"]) == 2
    assert client.post("/api/v1/auth/sessions/revoke-others", json={}, headers={**HEADERS,
        "x-csrf-token": result.json()["csrf_token"]}).status_code == 204
    with pytest.raises(AuthError, match="auth_required"):
        service.me(old)
    assert len(client.get("/api/v1/auth/sessions").json()["sessions"]) == 1


def test_failed_login_limits_are_durable(context):
    service, client, clock = context
    data = {"email": "nobody@example.invalid", "password": PASSWORD}
    for _ in range(service.policy.login_limit):
        assert client.post("/api/v1/auth/login", json=data, headers=HEADERS).status_code == 401
    result = client.post("/api/v1/auth/login", json=data, headers=HEADERS)
    assert result.status_code == 429 and int(result.headers["retry-after"]) > 0
    clock[0] += service.policy.rate_window
    assert client.post("/api/v1/auth/login", json=data, headers=HEADERS).status_code == 401


def test_body_limit_and_error_do_not_echo_secrets(context):
    service, client, _ = context
    result = client.post("/api/v1/auth/login", content=b'x' * 9000, headers={**HEADERS, "content-type": "application/json"})
    assert result.status_code == 413 and "x-request-id" in result.headers
    assert "x" * 100 not in result.text
    result = client.post("/api/v1/auth/login", json={"email": "bad", "password": "PRIVATE-SENTINEL"}, headers=HEADERS)
    assert result.status_code == 422 and "PRIVATE-SENTINEL" not in result.text


@pytest.mark.parametrize("raw", ["admin", "a" * 43, "null", "1", "я" * 43])
def test_forged_cookie_never_gives_identity(context, raw):
    service, client, _ = context
    client.cookies.set(service.policy.cookie_name, raw.encode("utf-8").hex() if not raw.isascii() else raw)
    assert client.get("/api/v1/auth/me", headers={"x-user-id": "admin"}).status_code == 401


def test_password_policy_and_disabled_registration(context):
    service, client, _ = context
    with pytest.raises(ValidationError):
        RegisterInput(**registration(service, password="short"))
    service.policy.registration = "disabled"
    assert client.post("/api/v1/auth/register", json=registration(service), headers=HEADERS).status_code == 403


def test_secure_cookie_policy_requires_https(context):
    service, _, _ = context
    with pytest.raises(ValidationError):
        AuthSettings(secure_cookie=True)
    policy = AuthSettings(secure_cookie=True, origins=("https://app.example.invalid",),
                          rate_secret="test-only" * 5)
    assert policy.cookie_name == "__Host-izo_session"


def test_secure_cookie_is_host_only_and_not_returned_as_json(context):
    service, _, _ = context
    service.policy = AuthSettings(registration="invite", secure_cookie=True,
        origins=("https://app.example.invalid",), rate_secret="test-rate-key-" * 4)
    app = create_app(Settings(), readiness=lambda: True)
    app.state.accounts_service = service
    with TestClient(app, base_url="https://app.example.invalid") as client:
        result = client.post("/api/v1/auth/register", json=registration(service),
                             headers={"origin": "https://app.example.invalid", "x-izo-request": "web"})
        assert result.status_code == 201
        cookie = result.headers["set-cookie"]
        assert cookie.startswith("__Host-izo_session=")
        assert "; Secure" in cookie and "; HttpOnly" in cookie and "Domain=" not in cookie
        assert client.cookies[service.policy.cookie_name] not in result.text
        assert client.get("/api/v1/auth/me").status_code == 200


def test_revoking_current_session_clears_cookie(context):
    service, client, _ = context
    data = signup(service, client).json()
    raw = client.cookies[service.policy.cookie_name]
    target = client.get("/api/v1/auth/sessions").json()["sessions"][0]["id"]
    result = client.delete(f"/api/v1/auth/sessions/{target}", headers={**HEADERS,
        "content-type": "application/json", "x-csrf-token": data["csrf_token"]})
    assert result.status_code == 204
    assert "Max-Age=0" in result.headers["set-cookie"]
    with pytest.raises(AuthError):
        service.me(raw)


def test_session_cap_and_policy_reduction(context):
    service, client, clock = context
    signup(service, client)
    service.policy.max_sessions = 1
    result = client.post("/api/v1/auth/login", json={"email": "alice@example.invalid", "password": PASSWORD}, headers=HEADERS)
    assert result.status_code == 409
    service.policy.idle_seconds = 60
    clock[0] += 60
    assert client.get("/api/v1/auth/me").status_code == 401


def test_permission_expiry_and_expired_invite(context):
    service, client, clock = context
    data = signup(service, client).json()
    raw = client.cookies[service.policy.cookie_name]
    with service.engine.begin() as conn:
        conn.execute(sa.insert(t.permissions).values(account_id=UUID(data["account"]["id"]),
            permission="admin.access", expires_at=clock[0]))
    with pytest.raises(AuthError, match="forbidden"):
        service.require_permission(raw, "admin.access")
    invitation = service.issue_invite(60)
    clock[0] += 60
    body = registration(service, "expired@example.invalid", invite_code=invitation)
    assert client.post("/api/v1/auth/register", json=body, headers=HEADERS).status_code == 400


def test_storage_or_sql_failure_does_not_emit_credentials(context, monkeypatch):
    service, client, _ = context
    def failure(*args, **kwargs):
        raise RuntimeError("PASSWORD-SENTINEL")
    monkeypatch.setattr(service, "me", failure)
    result = client.get("/api/v1/auth/me")
    assert result.status_code == 500
    assert "PASSWORD-SENTINEL" not in result.text
    assert result.headers["cache-control"] == "no-store"


def test_unknown_user_and_wrong_password_have_same_public_failure(context):
    service, client, _ = context
    signup(service, client)
    outputs = []
    for email in ["alice@example.invalid", "unknown@example.invalid"]:
        result = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong but same cost"}, headers=HEADERS)
        outputs.append((result.status_code, result.json()))
    assert outputs[0] == outputs[1] == (401, {"error": {"code": "invalid_credentials"}})


def test_chunked_body_limit(context):
    _, client, _ = context
    result = client.post("/api/v1/auth/login", content=iter([b"x" * 4000] * 3),
                         headers={**HEADERS, "content-type": "application/json"})
    assert result.status_code == 413


@pytest.mark.parametrize("state", ["generation_suspended", "deletion_pending"])
def test_restricted_accounts_cannot_use_staff_permission(context, state):
    service, client, _ = context
    value = signup(service, client).json()
    raw = client.cookies[service.policy.cookie_name]
    account_id = UUID(value["account"]["id"])
    with service.engine.begin() as conn:
        conn.execute(sa.insert(t.permissions).values(account_id=account_id, permission="admin.access"))
        conn.execute(sa.update(t.accounts).where(t.accounts.c.id == account_id).values(state=state))
    assert client.get("/api/v1/auth/me").status_code == 200
    with pytest.raises(AuthError, match="forbidden"):
        service.require_permission(raw, "admin.access")
