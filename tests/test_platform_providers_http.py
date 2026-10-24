"""P0-B1 real staff HTTP: encrypted key, verified status, auditing and denial."""
import base64
from uuid import uuid4
import sqlalchemy as sa
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from izo.accounts import tables as accounts
from izo.admin import tables as admin_tables
from izo.accounts.security import AuthError
from izo.accounts.http_security import AuthBodyLimit
from izo.chat.execution import FakeDeepSeekProvider
from izo.config import Settings
from izo.platform_providers import tables as platform
from izo.platform_providers.routes import attach_platform_providers
from test_admin import admin_env, password_hash, PASSWORD

BASE = "/api/v1/admin/providers"
KEY = "x" * 32
ROOT = base64.urlsafe_b64encode(b"r" * 32).decode("ascii").rstrip("=")


@pytest.fixture
def platform_http(admin_env, monkeypatch):
    admin, users, sessions = admin_env
    platform.metadata.create_all(admin.auth.engine)
    with admin.auth.engine.begin() as conn:
        for permission in ("connections.read", "connections.write", "secrets.bind"):
            conn.execute(sa.insert(accounts.permissions).values(
                account_id=users[0], permission=permission))
    monkeypatch.setenv("IZO_CHAT_ROOT_KEY", ROOT)
    app = FastAPI()

    @app.exception_handler(AuthError)
    async def auth_problem(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse({"error": {"code": "invalid_input"}}, status_code=422)

    attach_platform_providers(app, lambda request: admin.auth, Settings(environment="test"))
    app.add_middleware(AuthBodyLimit)
    with TestClient(app) as client:
        yield client, admin, users, sessions


def headers(env, user=0):
    _, service, _, sessions = env
    return {"Cookie": service.auth.policy.cookie_name + "=" + sessions[user].bearer,
            "Origin": "http://localhost:8080", "X-IZO-Request": "web",
            "X-CSRF-Token": sessions[user].view.csrf_token}


def replace(**change):
    return {"operation_id": str(uuid4()), "expected_revision": None,
            "key": KEY, "current_password": PASSWORD, **change}


def verify(revision, **change):
    return {"operation_id": str(uuid4()), "expected_revision": revision,
            "current_password": PASSWORD, **change}


def settings(revision, enabled=True, **change):
    return {"operation_id": str(uuid4()), "expected_revision": revision,
            "enabled": enabled, "model": "deepseek-flash", "daily_limit": 10,
            "concurrency_limit": 2, "current_password": PASSWORD, **change}


def test_nonstaff_and_anonymous_are_denied(platform_http):
    client, admin, users, _ = platform_http
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers=headers(platform_http, 2)).status_code == 403
    assert client.post(BASE + "/deepseek/credential", headers=headers(platform_http, 2),
                       json=replace()).status_code == 403
    with admin.auth.engine.begin() as conn:
        assert conn.execute(sa.select(admin_tables.events.c.actor_id).where(
            admin_tables.events.c.outcome == "denied")).scalar_one() == users[2]
    assert client.get(BASE, headers=headers(platform_http)).json() == {
        "connections": [{"provider": "deepseek", "configured": False,
            "enabled": False, "verified": False, "status": "not_configured",
            "model": "deepseek-flash", "revision": None, "generation": None,
            "daily_limit": 30, "concurrency_limit": 1, "available_to_users": False}]}


def test_key_write_verify_and_settings_survive_reopen(platform_http):
    client, admin, _, _ = platform_http
    session = headers(platform_http)
    created = client.post(BASE + "/deepseek/credential", headers=session, json=replace())
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["configured"] and not first["verified"] and not first["enabled"]
    assert first["available_to_users"] is False
    assert KEY not in created.text
    with admin.auth.engine.begin() as conn:
        row = conn.execute(sa.select(platform.connections)).mappings().one()
        assert KEY.encode() not in row["ciphertext"]
        assert b"x" * 32 not in row["ciphertext"]
    checked = client.post(BASE + "/deepseek/verify", headers=session,
                          json=verify(first["revision"]))
    assert checked.status_code == 200, checked.text
    verified = checked.json()
    assert verified["verified"] and not verified["enabled"]
    changed = client.patch(BASE + "/deepseek/config", headers=session,
                           json=settings(verified["revision"], model="deepseek-v4-pro"))
    assert changed.status_code == 200, changed.text
    state = changed.json()
    assert state["enabled"] and state["verified"] and state["model"] == "deepseek-v4-pro"
    assert state["available_to_users"] is False
    assert client.get(BASE, headers=session).json()["connections"][0] == state
    disabled = client.patch(BASE + "/deepseek/config", headers=session,
                            json=settings(state["revision"], enabled=False))
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    with admin.auth.engine.begin() as conn:
        events = conn.execute(sa.text("SELECT action FROM admin_events "
                                      "WHERE action LIKE 'platform.%'")).scalars().all()
        assert set(events) == {"platform.key.replaced", "platform.key.verified",
                               "platform.policy.changed"}


def test_replay_revision_and_rotation(platform_http):
    client, _, _, _ = platform_http
    h = headers(platform_http)
    command = replace()
    first = client.post(BASE + "/deepseek/credential", headers=h, json=command)
    assert first.status_code == 200
    assert client.post(BASE + "/deepseek/credential", headers=h, json=command).json() == first.json()
    changed = dict(command, key="z"*32)
    assert client.post(BASE + "/deepseek/credential", headers=h, json=changed).status_code == 409
    bad = client.post(BASE + "/deepseek/credential", headers=h,
                      json=replace(expected_revision=333))
    assert bad.status_code == 409
    rotation = client.post(BASE + "/deepseek/credential", headers=h,
                           json=replace(expected_revision=first.json()["revision"]))
    assert rotation.status_code == 200
    assert rotation.json()["generation"] == 2
    assert not rotation.json()["verified"]


@pytest.mark.parametrize("mutation", [
    {"Origin": "https://evil.invalid"},
    {"X-CSRF-Token": "wrong"},
    {"X-IZO-Request": ""},
    {"Sec-Fetch-Site": "cross-site"}])
def test_credential_mutations_reject_cross_origin_and_csrf(platform_http, mutation):
    client, _, _, _ = platform_http
    response = client.post(BASE + "/deepseek/credential",
        headers={**headers(platform_http), **mutation}, json=replace())
    assert response.status_code == 403, response.text


def test_secrets_and_password_never_appear_on_rejections(platform_http):
    client, admin, users, _ = platform_http
    h = headers(platform_http)
    wrong = client.post(BASE + "/deepseek/credential", headers=h,
        json=replace(current_password="wrong-password"))
    assert wrong.status_code == 403
    with admin.auth.engine.begin() as conn:
        assert conn.execute(sa.select(admin_tables.events.c.actor_id).where(
            admin_tables.events.c.outcome == "denied")).scalar_one() == users[0]
    invalid = client.post(BASE + "/deepseek/credential", headers=h,
        json={**replace(), "actor_id": str(uuid4())})
    assert invalid.status_code == 422
    assert KEY not in invalid.text and PASSWORD not in invalid.text
    assert client.get(BASE+"?with_secrets=1", headers=h).status_code == 422


def test_fake_verify_is_not_secret_saved(platform_http):
    client, _, _, _ = platform_http
    h = headers(platform_http)
    created = client.post(BASE + "/deepseek/credential", headers=h,
        json=replace(key="wrong-synthetic-key"))
    assert created.status_code == 200
    status = client.post(BASE + "/deepseek/verify", headers=h,
        json=verify(created.json()["revision"]))
    assert status.status_code == 422
    assert status.json() == {"error": {"code": "credential_rejected"}}
    assert not client.get(BASE, headers=h).json()["connections"][0]["verified"]


def test_revoked_staff_permission_denied_without_restart(platform_http):
    client, admin, users, _ = platform_http
    h = headers(platform_http)
    assert client.get(BASE, headers=h).status_code == 200
    with admin.auth.engine.begin() as conn:
        conn.execute(sa.delete(accounts.permissions).where(
            accounts.permissions.c.account_id == users[0],
            accounts.permissions.c.permission == "connections.read"))
    assert client.get(BASE, headers=h).status_code == 403


def test_rotation_disables_verified_active_connection(platform_http):
    client, _, _, _ = platform_http
    h = headers(platform_http)
    created = client.post(BASE + "/deepseek/credential", headers=h, json=replace()).json()
    checked = client.post(BASE + "/deepseek/verify", headers=h,
                          json=verify(created["revision"])).json()
    enabled = client.patch(BASE + "/deepseek/config", headers=h,
                           json=settings(checked["revision"])).json()
    assert enabled["enabled"] and enabled["verified"]
    rotated = client.post(BASE + "/deepseek/credential", headers=h,
                          json=replace(expected_revision=enabled["revision"], key="z"*32))
    assert rotated.status_code == 200
    assert rotated.json()["generation"] == 2
    assert not rotated.json()["enabled"] and not rotated.json()["verified"]
    attempted = client.patch(BASE + "/deepseek/config", headers=h,
                             json=settings(rotated.json()["revision"]))
    assert attempted.status_code == 409
    assert attempted.json() == {"error": {"code": "provider_not_verified"}}


def test_write_requires_secrets_bind_and_permissions_are_fresh(platform_http):
    client, admin, users, _ = platform_http
    h = headers(platform_http)
    with admin.auth.engine.begin() as conn:
        conn.execute(sa.delete(accounts.permissions).where(
            accounts.permissions.c.account_id == users[0],
            accounts.permissions.c.permission == "secrets.bind"))
    assert client.get(BASE, headers=h).status_code == 200
    assert client.post(BASE + "/deepseek/credential", headers=h, json=replace()).status_code == 403


def test_verify_rechecks_generation_after_remote_probe(platform_http):
    client, admin, _, _ = platform_http
    h = headers(platform_http)
    stored = client.post(BASE + "/deepseek/credential", headers=h, json=replace()).json()

    class RacingProbe:
        def verify(self, key, timeout=15):
            assert key == KEY
            with admin.auth.engine.begin() as conn:
                conn.execute(sa.update(platform.connections).values(
                    revision=platform.connections.c.revision + 1,
                    generation=platform.connections.c.generation + 1))

    client.app.state.platform_provider_adapter = RacingProbe()
    checked = client.post(BASE + "/deepseek/verify", headers=h,
                          json=verify(stored["revision"]))
    assert checked.status_code == 409
    assert checked.json() == {"error": {"code": "provider_changed_during_verify"}}
    assert client.get(BASE, headers=h).json()["connections"][0]["verified"] is False


def test_settings_exact_replay_does_not_increase_revision(platform_http):
    client, _, _, _ = platform_http
    h = headers(platform_http)
    first = client.post(BASE + "/deepseek/credential", headers=h, json=replace()).json()
    verified = client.post(BASE + "/deepseek/verify", headers=h,
                           json=verify(first["revision"])).json()
    command = settings(verified["revision"])
    updated = client.patch(BASE + "/deepseek/config", headers=h, json=command)
    assert updated.status_code == 200
    replay = client.patch(BASE + "/deepseek/config", headers=h, json=command)
    assert replay.status_code == 200 and replay.json() == updated.json()
    altered = dict(command, daily_limit=11)
    assert client.patch(BASE + "/deepseek/config", headers=h, json=altered).status_code == 409
