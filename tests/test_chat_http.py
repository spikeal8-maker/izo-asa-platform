"""CHAT-DEEPSEEK-001 HTTP boundary: same-origin, safe secret errors and SSE."""
from __future__ import annotations

import base64
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from izo.app import create_app
from izo.config import Settings
from izo.accounts import tables as accounts
from izo.accounts.schemas import RegisterInput
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.chat import tables as chat
from izo.chat.provider import FakeDeepSeekProvider
from izo.chat.service import ChatService
from izo.chat.schemas import ChatSettings

ORIGIN = "http://localhost:8080"
PASSWORD = "synthetic-chat-http-password"
KEY = "x" * 32


def root_key() -> str:
    return base64.urlsafe_b64encode(b"h" * 32).decode("ascii").rstrip("=")


@pytest.fixture
def http_env(tmp_path):
    engine = sa.create_engine(
        "sqlite:///" + str(tmp_path / "chat-http.sqlite"),
        connect_args={"check_same_thread": False},
    )

    @sa.event.listens_for(engine, "connect")
    def connect(db, _):
        db.execute("PRAGMA foreign_keys=ON")

    accounts.metadata.create_all(engine)
    chat.metadata.create_all(engine, tables=list(chat.TABLES))
    clock = [30_000]
    auth = AuthService(
        engine,
        AuthSettings(
            registration="open", rate_secret="chat-http-rate-" * 4,
            login_limit=100, network_limit=1000,
        ),
        clock=lambda: clock[0],
    )
    policy = ChatSettings(
        root_key=root_key(),
        preview_account_emails="alice@example.invalid,bob@example.invalid",
    )
    service = ChatService(
        auth, policy, FakeDeepSeekProvider(), clock=lambda: clock[0])
    app = create_app(Settings(environment="test"), readiness=lambda: True)
    app.state.accounts_service = auth
    app.state.chat_service = service
    with TestClient(app, base_url=ORIGIN) as client:
        yield auth, service, client
    engine.dispose()


def signup(auth, client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email, "password": PASSWORD,
            "display_name": email.split("@")[0],
        },
        headers={"Origin": ORIGIN, "X-IZO-Request": "web"},
    )
    assert response.status_code == 201, response.text
    client.headers.update({
        "Origin": ORIGIN,
        "X-IZO-Request": "web",
        "X-CSRF-Token": response.json()["csrf_token"],
    })
    return response.json()


def save_and_verify(client):
    saved = client.post(
        "/api/v1/chat/credential",
        json={"operation_id": str(uuid4()), "key": KEY},
    )
    assert saved.status_code == 200, saved.text
    verified = client.post(
        "/api/v1/chat/credential/verify",
        json={
            "operation_id": str(uuid4()),
            "expected_revision": saved.json()["revision"],
        },
    )
    assert verified.status_code == 200 and verified.json()["verified"]
    return verified.json()
def test_secret_write_is_safe_and_validation_never_echoes_key(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")

    bad = "sk-this-must-never-echo\nsecret"
    rejected = client.post(
        "/api/v1/chat/credential",
        json={"operation_id": str(uuid4()), "key": bad},
    )
    assert rejected.status_code == 422
    assert rejected.json() == {"error": {"code": "invalid_input"}}
    assert bad not in rejected.text and "secret" not in rejected.text

    saved = client.post(
        "/api/v1/chat/credential",
        json={"operation_id": str(uuid4()), "key": KEY},
    )
    assert saved.status_code == 200
    assert KEY not in saved.text
    assert "ciphertext" not in saved.text and "nonce" not in saved.text


def test_chat_mutations_require_origin_and_csrf(http_env):
    _, _, client = http_env
    account = signup(None, client, "alice@example.invalid")
    csrf = client.headers.pop("X-CSRF-Token")

    no_csrf = client.post(
        "/api/v1/chat/threads", json={"title": None})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "csrf_rejected"

    client.headers["X-CSRF-Token"] = csrf
    wrong = client.post(
        "/api/v1/chat/threads", json={"title": None},
        headers={"Origin": "https://wrong.invalid"},
    )
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "origin_rejected"
    assert account["account"]["email"] == "alice@example.invalid"


def test_http_durable_stream_duplicate_and_model_guard(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)

    policy = client.get("/api/v1/chat/policy")
    assert policy.status_code == 200
    assert [m["id"] for m in policy.json()["models"]] == [
        "deepseek-flash", "deepseek-v4-pro"]

    thread = client.post(
        "/api/v1/chat/threads", json={"title": None})
    assert thread.status_code == 201
    thread_id = thread.json()["id"]

    request_id = str(uuid4())
    body = {
        "request_id": request_id,
        "text": "HTTP stream",
        "model": "deepseek-flash",
    }
    first = client.post(
        f"/api/v1/chat/threads/{thread_id}/requests", json=body)
    replay = client.post(
        f"/api/v1/chat/threads/{thread_id}/requests", json=body)
    assert first.status_code == replay.status_code == 202
    assert first.json()["id"] == replay.json()["id"] == request_id

    conflict = client.post(
        f"/api/v1/chat/threads/{thread_id}/requests",
        json={**body, "text": "different"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "request_conflict"

    with client.stream(
            "GET", f"/api/v1/chat/requests/{request_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        stream = "".join(response.iter_text())
    assert "event: text.delta" in stream
    assert "event: message.done" in stream

    detail = client.get(f"/api/v1/chat/threads/{thread_id}")
    assert detail.status_code == 200
    assert detail.json()["messages"][-1]["state"] == "complete"
    assert "HTTP stream" in detail.json()["messages"][-1]["content"]

    blocked = client.post(
        f"/api/v1/chat/threads/{thread_id}/requests",
        json={
            "request_id": str(uuid4()), "text": "no",
            "model": "arbitrary-provider-model",
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "model_not_allowed"
def test_cross_account_http_hides_thread_and_request(http_env):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    save_and_verify(client)
    thread = client.post(
        "/api/v1/chat/threads", json={"title": "private"}).json()
    request_id = str(uuid4())
    request = client.post(
        f"/api/v1/chat/threads/{thread['id']}/requests",
        json={
            "request_id": request_id, "text": "secret",
            "model": "deepseek-flash",
        },
    )
    assert request.status_code == 202

    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    signup(auth, client, "bob@example.invalid")
    save_and_verify(client)

    assert client.get(
        f"/api/v1/chat/threads/{thread['id']}").status_code == 404
    assert client.get(
        f"/api/v1/chat/requests/{request_id}").status_code == 404
    foreign = client.post(
        f"/api/v1/chat/threads/{thread['id']}/requests",
        json={
            "request_id": str(uuid4()), "text": "steal",
            "model": "deepseek-flash",
        },
    )
    assert foreign.status_code == 404


def test_http_stop_pending_is_terminal_and_idempotent(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    thread = client.post(
        "/api/v1/chat/threads", json={"title": None}).json()
    request_id = str(uuid4())
    created = client.post(
        f"/api/v1/chat/threads/{thread['id']}/requests",
        json={
            "request_id": request_id, "text": "stop",
            "model": "deepseek-flash",
        },
    )
    assert created.status_code == 202

    stopped = client.post(
        f"/api/v1/chat/requests/{request_id}/stop", json={})
    repeated = client.post(
        f"/api/v1/chat/requests/{request_id}/stop", json={})
    assert stopped.status_code == repeated.status_code == 200
    assert stopped.json()["state"] == repeated.json()["state"] == "stopped"

    with client.stream(
            "GET", f"/api/v1/chat/requests/{request_id}/events") as response:
        stream = "".join(response.iter_text())
    assert "message.interrupted" in stream
    assert "text.delta" not in stream

def test_preview_compression_metadata_and_secret_exclusion(tmp_path, monkeypatch):
    import gzip
    import zipfile
    from pathlib import Path
    from tools import build_preview as builder
    def fake_run(*args):
        if args[1] == 'save':
            Path(args[3]).write_bytes(b'synthetic image archive')
    monkeypatch.setattr(builder, 'run', fake_run)
    bundle, info = builder.write_bundle(tmp_path, sha='a' * 40, source_sha='b' * 40,
        api_image='test-api:local', web_image='test-web:local', live_status='NOT_RUN')
    assert (info['build_sha'], info['source_sha']) == ('a' * 40, 'b' * 40)
    assert gzip.decompress((bundle / 'images.tar').read_bytes()) == b'synthetic image archive'
    (bundle / '.env').write_text('synthetic-private-config', encoding='ascii')
    archive, _, digest = builder.archive(tmp_path, bundle)
    with zipfile.ZipFile(archive) as checked:
        assert len(checked.namelist()) == 7 and not any(n.endswith('.env') for n in checked.namelist())
    assert digest == builder.sha256(archive)
