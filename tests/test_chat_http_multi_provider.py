"""Provider-aware HTTP Chat policy and durable stream acceptance."""
from uuid import uuid4

from test_chat_http import http_env, save_and_verify, signup


def test_http_durable_stream_duplicate_and_model_guard(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)

    policy = client.get("/api/v1/chat/policy")
    assert policy.status_code == 200
    assert [(m["id"], m["provider"]) for m in policy.json()["models"]] == [
        ("deepseek-flash", "deepseek"),
        ("deepseek-v4-pro", "deepseek"),
        ("openrouter-auto", "openrouter"),
    ]

    thread = client.post("/api/v1/chat/threads", json={"title": None})
    assert thread.status_code == 201
    thread_id = thread.json()["id"]
    request_id = str(uuid4())
    body = {
        "request_id": request_id, "text": "HTTP stream",
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
        json={**body, "text": "different"})
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
        })
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "model_not_allowed"
