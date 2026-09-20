"""Accounts registration, credential and public-boundary tests."""
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from izo.app import create_app
from izo.config import Settings
from izo.accounts import tables as t
from izo.accounts.settings import AuthSettings
from izo.accounts.schemas import RegisterInput
from test_accounts_support import context, registration, signup, HEADERS, ORIGIN, PASSWORD


@pytest.mark.parametrize("field,value", [("role", "admin"), ("permissions", ["admin.access"]),
                                        ("balance", 9999), ("owner_id", "forged")])
def test_signup_does_not_accept_privileges(context, field, value):
    service, client, _ = context
    result = client.post("/api/v1/auth/register", json=registration(service, **{field: value}), headers=HEADERS)
    assert result.status_code == 422 and PASSWORD not in result.text
    with service.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.accounts)).scalar_one() == 0


@pytest.mark.parametrize("changes", [{}, {"origin": "https://evil.invalid"},
    {"origin": ORIGIN + ".evil.invalid", "x-izo-request": "web"},
    {**HEADERS, "sec-fetch-site": "cross-site"}, {"origin": "null", "x-izo-request": "web"}])
def test_login_csrf_and_missing_origin_are_blocked(context, changes):
    service, client, _ = context
    assert client.post("/api/v1/auth/register", json=registration(service), headers=changes).status_code == 403


def test_open_registration_and_email_canonicalization(context):
    service, client, _ = context
    assert client.post("/api/v1/auth/register", json=registration(service, " ALICE@EXAMPLE.INVALID "), headers=HEADERS).status_code == 201
    client.cookies.clear()
    assert client.post("/api/v1/auth/register", json=registration(service), headers=HEADERS).status_code == 400
    assert client.post("/api/v1/auth/register", json=registration(service, "other@example.invalid"), headers=HEADERS).status_code == 201


def test_invite_mode_remains_operator_only_and_single_use(context):
    service, client, _ = context
    service.policy.registration = "invite"
    assert client.post("/api/v1/auth/register", json=registration(service), headers=HEADERS).status_code == 400
    invitation = service.issue_invite()
    body = registration(service, invite_code=invitation)
    assert client.post("/api/v1/auth/register", json=body, headers=HEADERS).status_code == 201
    client.cookies.clear(); body["email"] = "other@example.invalid"
    assert client.post("/api/v1/auth/register", json=body, headers=HEADERS).status_code == 400


def test_body_limit_and_error_do_not_echo_secrets(context):
    _, client, _ = context
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
    with pytest.raises(ValidationError): RegisterInput(**registration(service, password="1234567"))
    assert RegisterInput(**registration(service, password="12345678"))
    service.policy.registration = "disabled"
    assert client.post("/api/v1/auth/register", json=registration(service), headers=HEADERS).status_code == 403


def test_secure_cookie_policy_requires_https(context):
    with pytest.raises(ValidationError): AuthSettings(secure_cookie=True)
    policy = AuthSettings(secure_cookie=True, origins=("https://app.example.invalid",), rate_secret="test-only" * 5)
    assert policy.cookie_name == "__Host-izo_session"


def test_secure_cookie_is_host_only_and_not_returned_as_json(context):
    service, _, _ = context
    service.policy = AuthSettings(registration="open", secure_cookie=True,
        origins=("https://app.example.invalid",), rate_secret="test-rate-key-" * 4)
    app = create_app(Settings(), readiness=lambda: True); app.state.accounts_service = service
    with TestClient(app, base_url="https://app.example.invalid") as client:
        result = client.post("/api/v1/auth/register", json=registration(service),
                             headers={"origin": "https://app.example.invalid", "x-izo-request": "web"})
        assert result.status_code == 201
        cookie = result.headers["set-cookie"]
        assert cookie.startswith("__Host-izo_session=")
        assert "; Secure" in cookie and "; HttpOnly" in cookie and "Domain=" not in cookie
        assert client.cookies[service.policy.cookie_name] not in result.text
        assert client.get("/api/v1/auth/me").status_code == 200


def test_unknown_user_and_wrong_password_have_same_public_failure(context):
    service, client, _ = context
    signup(service, client); outputs = []
    for email in ["alice@example.invalid", "unknown@example.invalid"]:
        result = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong but same cost"}, headers=HEADERS)
        outputs.append((result.status_code, result.json()))
    assert outputs[0] == outputs[1] == (401, {"error": {"code": "invalid_credentials"}})


def test_chunked_body_limit(context):
    _, client, _ = context
    result = client.post("/api/v1/auth/login", content=iter([b"x" * 4000] * 3),
                         headers={**HEADERS, "content-type": "application/json"})
    assert result.status_code == 413

def test_registration_creates_unverified_session_and_login_needs_no_email_delivery(context):
    service, client, _ = context
    created = client.post("/api/v1/auth/register", json=registration(service), headers=HEADERS)
    assert created.status_code == 201
    assert created.json()["account"]["email_verified"] is False
    csrf = created.json()["csrf_token"]
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["account"]["email_verified"] is False
    assert client.post("/api/v1/auth/logout", json={}, headers={**HEADERS, "x-csrf-token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    logged = client.post("/api/v1/auth/login",
        json={"email": "alice@example.invalid", "password": PASSWORD}, headers=HEADERS)
    assert logged.status_code == 200
    assert logged.json()["account"]["email_verified"] is False
