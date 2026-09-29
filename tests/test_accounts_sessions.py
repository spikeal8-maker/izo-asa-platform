"""Accounts session, permission and revocation tests."""
from uuid import UUID

import pytest
import sqlalchemy as sa

from izo.accounts import tables as t
from izo.accounts.security import AuthError
from test_accounts_support import context, registration, signup, HEADERS, PASSWORD


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
        conn.execute(sa.insert(t.permissions).values(account_id=UUID(a["account"]["id"]), permission="admin.access"))
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
        if expiration == "idle": clock[0] += service.policy.idle_seconds
        elif expiration == "absolute":
            clock[0] += 1; conn.execute(sa.update(t.sessions).values(expires_at=clock[0]))
        elif expiration == "revoked": conn.execute(sa.update(t.sessions).values(revoked_at=clock[0]))
        else: conn.execute(sa.update(t.accounts).values(state="security_locked"))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rotates_bearer_and_revoke_others(context):
    service, client, _ = context
    signup(service, client)
    old = client.cookies[service.policy.cookie_name]
    result = client.post("/api/v1/auth/login", json={"email": "alice@example.invalid", "password": PASSWORD}, headers=HEADERS)
    assert result.status_code == 200 and client.cookies[service.policy.cookie_name] != old
    assert len(client.get("/api/v1/auth/sessions").json()["sessions"]) == 2
    assert client.post("/api/v1/auth/sessions/revoke-others", json={}, headers={**HEADERS,
        "x-csrf-token": result.json()["csrf_token"]}).status_code == 204
    with pytest.raises(AuthError, match="auth_required"): service.me(old)
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


def test_revoking_current_session_clears_cookie(context):
    service, client, _ = context
    data = signup(service, client).json(); raw = client.cookies[service.policy.cookie_name]
    target = client.get("/api/v1/auth/sessions").json()["sessions"][0]["id"]
    result = client.delete(f"/api/v1/auth/sessions/{target}", headers={**HEADERS,
        "content-type": "application/json", "x-csrf-token": data["csrf_token"]})
    assert result.status_code == 204 and "Max-Age=0" in result.headers["set-cookie"]
    with pytest.raises(AuthError): service.me(raw)


def test_session_cap_and_policy_reduction(context):
    service, client, clock = context
    signup(service, client); service.policy.max_sessions = 1
    result = client.post("/api/v1/auth/login", json={"email": "alice@example.invalid", "password": PASSWORD}, headers=HEADERS)
    assert result.status_code == 409
    service.policy.idle_seconds = 60; clock[0] += 60
    assert client.get("/api/v1/auth/me").status_code == 401


def test_permission_expiry_and_expired_invite(context):
    service, client, clock = context
    data = signup(service, client).json(); raw = client.cookies[service.policy.cookie_name]
    with service.engine.begin() as conn:
        conn.execute(sa.insert(t.permissions).values(account_id=UUID(data["account"]["id"]), permission="admin.access", expires_at=clock[0]))
    with pytest.raises(AuthError, match="forbidden"): service.require_permission(raw, "admin.access")
    service.policy.registration = "invite"
    invitation = service.issue_invite(60); clock[0] += 60
    body = registration(service, "expired@example.invalid", invite_code=invitation)
    assert client.post("/api/v1/auth/register", json=body, headers=HEADERS).status_code == 400


def test_storage_or_sql_failure_does_not_emit_credentials(context, monkeypatch):
    service, client, _ = context
    def failure(*args, **kwargs): raise RuntimeError("PASSWORD-SENTINEL")
    monkeypatch.setattr(service, "me", failure)
    result = client.get("/api/v1/auth/me")
    assert result.status_code == 500 and "PASSWORD-SENTINEL" not in result.text
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("state", ["generation_suspended", "deletion_pending"])
def test_restricted_accounts_cannot_use_staff_permission(context, state):
    service, client, _ = context
    value = signup(service, client).json(); raw = client.cookies[service.policy.cookie_name]
    account_id = UUID(value["account"]["id"])
    with service.engine.begin() as conn:
        conn.execute(sa.insert(t.permissions).values(account_id=account_id, permission="admin.access"))
        conn.execute(sa.update(t.accounts).where(t.accounts.c.id == account_id).values(state=state))
    assert client.get("/api/v1/auth/me").status_code == 200
    with pytest.raises(AuthError, match="forbidden"): service.require_permission(raw, "admin.access")
