"""Thread rename uses the existing safe same-origin HTTP mutation boundary."""
import json
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from izo.chat import tables as chat
from test_chat_http import ORIGIN, http_env, signup, save_and_verify


def create_thread(client):
    result = client.post("/api/v1/chat/threads", json={"title": None})
    assert result.status_code == 201
    return result.json()


def test_http_rename_reload_and_first_send_preserve_manual_title(http_env):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = create_thread(client)
    path = f"/api/v1/chat/threads/{thread['id']}"
    renamed = client.patch(path, json={"title": " \ufeffНовый чат\u3000 "})
    assert renamed.status_code == 200
    assert renamed.json() == thread
    assert set(renamed.json()) == {"id", "title", "created_at", "updated_at"}
    save_and_verify(client)
    request_id = str(uuid4())
    admitted = client.post(f"{path}/requests", json={
        "request_id": request_id, "text": "Do not replace my chosen title", "model": "deepseek-flash"})
    assert admitted.status_code == 202
    detail = client.get(path)
    assert detail.status_code == 200
    assert detail.json()["thread"]["title"] == "Новый чат"
    assert all(item["request_id"] == request_id for item in detail.json()["messages"])
    assert client.get("/api/v1/chat/threads").json()["threads"][0]["title"] == "Новый чат"


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": " \n\t\u3000"},
    {"title": "\u0085"}, {"title": "\ufeff"}, {"title": " \ufeff\u0085 "}, {"title": "\ufeff\x1c"},
    {"title": "\u0085\ufeff\u0085"}, {"title": "\x1c\ufeff\x1c"},
    {"title": "я" * 121}, {"title": "😀" * 121},
    {"title": None}, {"title": 123}, {"title": True}, {"title": []}, {"title": {}},
    {"title": "secret\x00value"}, {"title": "secret\ud800value"},
    {"title": "secret\udfffvalue"}, {"title": "valid", "account_id": str(uuid4())},
    {"title": "valid", "title_is_manual": False}])
def test_http_invalid_title_is_safe_and_does_not_mutate(http_env, body):
    auth, service, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = create_thread(client)
    path = f"/api/v1/chat/threads/{thread['id']}"
    # ASCII JSON escapes exercise invalid Unicode through the actual HTTP parser.
    response = client.patch(path, content=json.dumps(body, ensure_ascii=True),
                            headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "invalid_input"}}
    assert client.get(path).json()["thread"] == thread
    with service.engine.connect() as conn:
        assert conn.execute(sa.select(chat.threads.c.title_is_manual).where(
            chat.threads.c.id == UUID(thread["id"]))).scalar_one() is False


@pytest.mark.parametrize("title", ["я" * 120, "😀" * 120, "\ufeff " + "😀" * 120 + "\u3000"])
def test_http_accepts_120_code_points_after_browser_compatible_trim(http_env, title):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = create_thread(client)
    path = f"/api/v1/chat/threads/{thread['id']}"
    response = client.patch(path, json={"title": title})
    assert response.status_code == 200
    assert len(response.json()["title"]) == 120
    assert client.get(path).json()["thread"] == response.json()


def test_http_mixed_visible_title_is_preserved(http_env):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = create_thread(client)
    title = "\u0085\ufeffX\u0085"
    response = client.patch(f"/api/v1/chat/threads/{thread['id']}", json={"title": title})
    assert response.status_code == 200
    assert response.json()["title"] == title


@pytest.mark.parametrize("boundary", ["missing_csrf", "wrong_csrf", "wrong_origin", "missing_origin", "anonymous"])
def test_http_rename_auth_origin_and_csrf_boundaries(http_env, boundary):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = create_thread(client)
    path = f"/api/v1/chat/threads/{thread['id']}"
    if boundary == "missing_csrf":
        client.headers.pop("X-CSRF-Token")
    elif boundary == "wrong_csrf":
        client.headers["X-CSRF-Token"] = "wrong"
    elif boundary == "wrong_origin":
        client.headers["Origin"] = "https://untrusted.invalid"
    elif boundary == "missing_origin":
        client.headers.pop("Origin")
    else:
        client.cookies.clear()
    response = client.patch(path, json={"title": "unauthorized"})
    assert response.status_code == (401 if boundary == "anonymous" else 403)
    expected = "origin_rejected" if "origin" in boundary else "csrf_rejected"
    if boundary != "anonymous":
        assert response.json() == {"error": {"code": expected}}
    if boundary != "anonymous":
        client.headers["Origin"] = ORIGIN
        assert client.get(path).json()["thread"] == thread


def test_http_foreign_thread_matches_missing_and_owner_data_unchanged(http_env):
    auth, service, client = http_env
    signup(auth, client, "alice@example.invalid")
    thread = create_thread(client)
    owner_cookies = dict(client.cookies)
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    signup(auth, client, "bob@example.invalid")
    path = f"/api/v1/chat/threads/{thread['id']}"
    foreign = client.patch(path, json={"title": "foreign rename"})
    missing = client.patch(f"/api/v1/chat/threads/{uuid4()}", json={"title": "foreign rename"})
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"error": {"code": "thread_not_found"}}
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    assert client.get(path).json()["thread"] == thread
    with service.engine.connect() as conn:
        assert conn.execute(sa.select(chat.threads.c.title_is_manual).where(
            chat.threads.c.id == UUID(thread["id"]))).scalar_one() is False
