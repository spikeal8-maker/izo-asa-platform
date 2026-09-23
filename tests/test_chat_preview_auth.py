"""Local Docker preview auth repair acceptance."""
from __future__ import annotations

import base64
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from izo.app import create_app
from izo.config import Settings
from izo.accounts import tables as accounts
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.chat import tables as chat
from izo.chat.provider import FakeDeepSeekProvider
from izo.chat.schemas import ChatSettings
from izo.chat.service import ChatService

ORIGIN = "http://localhost:8080"
PASSWORD = "synthetic-preview-password"
KEY = "x" * 32

def root_key() -> str:
    return base64.urlsafe_b64encode(b"p" * 32).decode("ascii").rstrip("=")

@pytest.fixture
def preview_env(tmp_path):
    engine = sa.create_engine(
        "sqlite:///" + str(tmp_path / "preview.sqlite"),
        connect_args={"check_same_thread": False})
    @sa.event.listens_for(engine, "connect")
    def connect(db, _):
        db.execute("PRAGMA foreign_keys=ON")
    accounts.metadata.create_all(engine)
    chat.metadata.create_all(engine, tables=list(chat.TABLES))
    clock = [40_000]
    auth = AuthService(engine, AuthSettings(
        registration="open", rate_secret="preview-rate-" * 4,
        login_limit=100, network_limit=1000), clock=lambda: clock[0])
    service = ChatService(auth, ChatSettings(
        root_key=root_key(), preview_account_emails="preview@local.izo",
        local_preview_enabled=True), FakeDeepSeekProvider(), clock=lambda: clock[0])
    app = create_app(Settings(environment="test"), readiness=lambda: True)
    app.state.accounts_service = auth
    app.state.chat_service = service
    with TestClient(app, base_url=ORIGIN) as client:
        yield service, client
    engine.dispose()

def headers(csrf: str | None = None):
    result = {"Origin": ORIGIN, "X-IZO-Request": "web"}
    if csrf:
        result["X-CSRF-Token"] = csrf
    return result

def signup(client, email: str):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD,
        "display_name": email.split("@")[0]}, headers=headers())
    assert response.status_code == 201, response.text
    client.headers.update(headers(response.json()["csrf_token"]))
    return response.json()

def preview_login(client):
    client.cookies.clear()
    client.headers.clear()
    response = client.post(
        "/api/v1/auth/local-preview", json={}, headers=headers())
    assert response.status_code == 200, response.text
    client.headers.update(headers(response.json()["csrf_token"]))
    return response.json()

def save_and_verify(client):
    saved = client.post("/api/v1/chat/credential", json={
        "operation_id": str(uuid4()), "key": KEY})
    assert saved.status_code == 200, saved.text
    verified = client.post("/api/v1/chat/credential/verify", json={
        "operation_id": str(uuid4()),
        "expected_revision": saved.json()["revision"]})
    assert verified.status_code == 200 and verified.json()["verified"]
    return verified.json()

def test_local_preview_reuses_account_history_and_credential(preview_env):
    _, client = preview_env
    legacy = signup(client, "preview@local.izo")
    credential = save_and_verify(client)
    thread = client.post("/api/v1/chat/threads", json={"title": "preview"}).json()
    request_id = str(uuid4())
    created = client.post(
        f"/api/v1/chat/threads/{thread['id']}/requests", json={
            "request_id": request_id, "text": "persist me",
            "model": "deepseek-flash"})
    assert created.status_code == 202
    with client.stream(
            "GET", f"/api/v1/chat/requests/{request_id}/events") as response:
        assert response.status_code == 200
        assert "message.done" in "".join(response.iter_text())
    second = preview_login(client)
    assert second["account"]["id"] == legacy["account"]["id"]
    current = client.get("/api/v1/chat/credential").json()
    assert current["revision"] == credential["revision"]
    reverified = client.post("/api/v1/chat/credential/verify", json={
        "operation_id": str(uuid4()),
        "expected_revision": current["revision"]})
    assert reverified.status_code == 200 and reverified.json()["verified"]
    detail = client.get(f"/api/v1/chat/threads/{thread['id']}").json()
    assert any(m["content"] == "persist me" for m in detail["messages"])

def test_local_preview_off_keeps_normal_auth_and_chat_closed(preview_env):
    service, client = preview_env
    service.policy.local_preview_enabled = False
    client.cookies.clear()
    client.headers.clear()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/chat/policy").status_code == 401
    assert client.post(
        "/api/v1/auth/local-preview", json={}, headers=headers()).status_code == 404
    registered = client.post("/api/v1/auth/register", json={
        "email": "normal@example.invalid", "password": PASSWORD,
        "display_name": "normal"}, headers=headers())
    assert registered.status_code == 201
    client.cookies.clear()
    logged_in = client.post("/api/v1/auth/login", json={
        "email": "normal@example.invalid", "password": PASSWORD}, headers=headers())
    assert logged_in.status_code == 200

