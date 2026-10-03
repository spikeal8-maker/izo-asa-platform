"""P1 account-owned history pages and stable sequence cursors."""
import pytest
import sqlalchemy as sa
from uuid import uuid4

from izo.chat import tables as chat
from izo.chat.service import ChatError
from test_chat import chat_env, connect_key, new_thread, request
from test_chat_http import http_env, signup, save_and_verify


def test_pages_remain_stable_when_new_messages_arrive(chat_env):
    service, alice, bob, _ = chat_env
    connect_key(service, alice)
    thread = new_thread(service, alice)
    for index in range(101):
        created = request(service, alice, thread.id, f"Question {index}")
        assert "message.done" in "".join(service.stream_events(alice.bearer, created.id))
        with service.engine.begin() as conn:
            conn.execute(sa.delete(chat.limits))

    latest = service.thread_detail(alice.bearer, thread.id)
    assert [item.sequence for item in latest.messages] == list(range(103, 203))
    assert latest.next_before_sequence == 103
    created = request(service, alice, thread.id, "Appended while reading")
    assert "message.done" in "".join(service.stream_events(alice.bearer, created.id))
    older = service.older_messages(alice.bearer, thread.id, latest.next_before_sequence)
    assert [item.sequence for item in older.messages] == list(range(3, 103))
    assert older.next_before_sequence == 3
    first = service.older_messages(alice.bearer, thread.id, older.next_before_sequence)
    assert [item.sequence for item in first.messages] == [1, 2]
    assert first.next_before_sequence is None
    assert len({item.id for item in latest.messages + older.messages + first.messages}) == 202
    assert service.older_messages(alice.bearer, thread.id, 1).messages == []
    with pytest.raises(ChatError, match="thread_not_found"):
        service.older_messages(bob.bearer, thread.id, 3)


def test_http_page_cursor_validation_and_foreign_thread(http_env):
    auth, _, client = http_env
    signup(auth, client, "alice@example.invalid")
    save_and_verify(client)
    thread = client.post("/api/v1/chat/threads", json={"title": "private"}).json()
    request_id = str(uuid4())
    admitted = client.post(f"/api/v1/chat/threads/{thread['id']}/requests", json={
        "request_id": request_id, "text": "secret", "model": "deepseek-flash"})
    assert admitted.status_code == 202
    path = f"/api/v1/chat/threads/{thread['id']}/messages"
    page = client.get(f"{path}?before_sequence=2")
    assert page.status_code == 200
    assert [item["sequence"] for item in page.json()["messages"]] == [1]
    assert page.json()["next_before_sequence"] is None
    assert client.get(path).status_code == 422
    assert client.get(f"{path}?before_sequence=0").status_code == 422
    assert client.get(f"{path}?before_sequence=9223372036854775808").status_code == 422
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    signup(auth, client, "bob@example.invalid")
    assert client.get(f"{path}?before_sequence=2").status_code == 404
