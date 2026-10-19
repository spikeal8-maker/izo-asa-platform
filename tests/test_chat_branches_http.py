"""Edit HTTP authorization, admission and retained branch history."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.chat import tables as t
from izo.chat.graph_requests import admit_request
from izo.chat.history_pages import graph_page
from izo.chat.service import ChatError, ChatService
from test_chat import chat_env, new_thread, request
from test_chat_branches import durable_rows, edit, edit_command, send, switch
from test_chat_graph_context import finish
from test_chat_graph_http import BASE, commands, completed_thread
from test_chat_graph_requests import prepare, regenerate
from test_chat_http import http_env, save_and_verify, signup
from test_chat_vision import asset, submit, vision_env


def setup(client):
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    return completed_thread(client)


def payload(graph, text="Исправленный вопрос"):
    turn, command, _ = commands(graph)
    return f"/turns/{turn['id']}/edit", {**command, "text": text}


def test_http_edit_restore_fenced_send(http_env):
    _, _, client = http_env
    path, original = setup(client)
    root = original["active_branch_id"]
    history = client.get(path).json()["messages"]
    endpoint, command = payload(original)
    response = client.post(path + endpoint, json=command)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["request"]["id"] == command["request_id"]
    assert accepted["created_branch"]["parent_branch_id"] == root
    child = client.get(f"{path}/graph?branch_id={accepted['active_branch_id']}").json()
    assert child["turns"][0]["id"] == accepted["turn_id"]
    assert child["turns"][0]["selected_attempt_id"] is None
    assert client.get(path).json()["messages"][:2] == history
    old_read = client.get(f"{path}/graph?branch_id={root}")
    assert old_read.status_code == 409
    assert client.get(f"{BASE}/requests/{command['request_id']}/events").status_code == 200
    child = client.get(f"{path}/graph").json()
    switched = client.patch(f"{path}/branch-selection", json={"branch_id": child["active_branch_id"],
        "target_branch_id": root, "expected_revision": child["revision"]})
    assert switched.status_code == 200 and switched.json()["turns"] == original["turns"]
    restored = switched.json()
    replay = client.post(path + endpoint, json=command)
    assert replay.status_code == 202 and replay.json()["request"]["state"] == "completed"
    assert replay.json()["created_branch"] == accepted["created_branch"]
    assert replay.json()["active_branch_id"] == root
    body = {"request_id": str(uuid4()), "text": "Продолжение", "model": "deepseek-flash"}
    assert client.post(f"{path}/requests", json=body).json()["error"]["code"] == "branch_selection_required"
    assert client.post(f"{path}/requests", json={**body, "branch_id": child["active_branch_id"],
        "expected_revision": child["revision"]}).status_code == 409
    for field in ("branch_id", "expected_revision"):
        assert client.post(f"{path}/requests", json={**body, field: restored[
            "active_branch_id" if field == "branch_id" else "revision"]}).status_code == 422
    sent = client.post(f"{path}/requests", json={**body, "branch_id": restored["active_branch_id"],
        "expected_revision": restored["revision"]})
    assert sent.status_code == 202 and "request" not in sent.json()
    for private in ("snapshot", "fingerprint", "fork_source_attempt_id", "credential_generation"):
        assert private not in response.text + client.get(f"{path}/branches").text


@pytest.mark.parametrize("mutation", ["edit", "branch-selection"])
@pytest.mark.parametrize("boundary", ["origin", "csrf", "session"])
def test_http_mutation_security(http_env, mutation, boundary):
    _, service, client = http_env
    path, graph = setup(client)
    endpoint, command = payload(graph)
    if mutation == "branch-selection":
        endpoint = "/branch-selection"
        command = {"branch_id": graph["active_branch_id"], "target_branch_id": graph["active_branch_id"],
                   "expected_revision": graph["revision"]}
    before = durable_rows(service)
    headers = {"Origin": "https://foreign.invalid"} if boundary == "origin" else {}
    if boundary == "csrf":
        client.headers.pop("X-CSRF-Token")
    if boundary == "session":
        client.cookies.clear()
    result = client.request("POST" if mutation == "edit" else "PATCH", path + endpoint,
        json=command, headers=headers)
    assert result.status_code == (401 if boundary == "session" else 403)
    assert durable_rows(service) == before


def test_http_foreign_identities_before_cas(http_env):
    _, service, client = http_env
    path, graph = setup(client)
    endpoint, command = payload(graph)
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    signup(None, client, "bob@example.invalid")
    save_and_verify(client)
    own, owned = completed_thread(client, "Bob")
    target, body = payload(owned)
    before = durable_rows(service)
    assert client.post(path + endpoint, json=command).status_code == 404
    assert client.get(f"{path}/branches").status_code == 404
    assert client.get(f"{own}/graph?branch_id={graph['active_branch_id']}").status_code == 404
    assert client.post(own + endpoint, json=body).status_code == 404
    for change in ({"branch_id": graph["active_branch_id"]},
                   {"source_attempt_id": graph["turns"][0]["selected_attempt_id"]},
                   {"request_id": graph["turns"][0]["selected_attempt_id"]}):
        assert client.post(own + target, json={**body, **change, "expected_revision": 0}).status_code == 404
    assert client.patch(f"{own}/branch-selection", json={"branch_id": owned["active_branch_id"],
        "target_branch_id": graph["active_branch_id"], "expected_revision": 0}).status_code == 404
    assert durable_rows(service) == before


@pytest.mark.parametrize("change", [{"text": ""}, {"text": "\0"}, {"text": "x" * 6001},
    {"expected_revision": -1}, {"model": "deepseek-flash"}, {"attachment_ids": []}],
    ids=["empty", "nul", "raw-6001", "negative-revision", "model-extra", "attachments-extra"])
def test_http_invalid_edit_keeps_uuid(http_env, change):
    _, service, client = http_env
    path, graph = setup(client)
    endpoint, command = payload(graph)
    before = durable_rows(service)
    assert client.post(path + endpoint, json={**command, **change}).status_code == 422
    assert durable_rows(service) == before
    assert client.post(path + endpoint, json=command).status_code == 202


def test_unchanged_edit_is_noop(chat_env, monkeypatch):
    service, alice, _, _ = chat_env
    thread, _, _ = prepare(service, alice)
    first_turn = graph_page(service, alice.bearer, thread.id).turns[0].id
    pending = request(service, alice, thread.id, "Expired pending")
    with service.engine.begin() as conn:
        conn.execute(sa.update(t.requests).where(t.requests.c.id == pending.id).values(deadline_at=0))
        conn.execute(sa.update(t.connections).values(enabled=False))
    source, command = edit_command(service, alice, thread.id, "\u0085Исходный вопрос\x1c", first_turn)
    before = durable_rows(service)
    with monkeypatch.context() as patch:
        patch.setattr(service, "_consume_rate", lambda *_: pytest.fail("Unchanged edit consumed rate"))
        patch.setattr(service, "_attachment_assets", lambda *_: pytest.fail("Unchanged edit admitted assets"))
        with pytest.raises(ChatError, match="message_unchanged"):
            admit_request(service, alice.bearer, alice.view.csrf_token, thread.id, command, source, edit=True)
    assert durable_rows(service) == before
    with service.engine.begin() as conn:
        conn.execute(sa.update(t.connections).values(enabled=True))
    accepted = admit_request(service, alice.bearer, alice.view.csrf_token, thread.id,
        command.model_copy(update={"text": "Changed"}), source, edit=True)
    assert accepted.request.id == command.request_id


def test_unknown_survives_branch_reload(chat_env):
    service, alice, _, _ = chat_env
    thread, _, _ = prepare(service, alice)
    accepted, _, _ = edit(service, alice, thread.id, "Unknown child")
    service.provider.failure = "provider_connection_failed"
    assert "message.error" in "".join(service.stream_events(alice.bearer, accepted.request.id))
    restored = switch(service, alice, thread.id, thread.id)
    assert restored.unknown_request_id == accepted.request.id
    restarted = ChatService(service.auth, service.policy, service.provider, clock=service.clock)
    page = graph_page(restarted, alice.bearer, thread.id)
    assert page.active_branch_id == thread.id and page.unknown_request_id == accepted.request.id
    for operation in (lambda: send(restarted, alice, thread.id, "New"),
                      lambda: edit(restarted, alice, thread.id, "Edited again"),
                      lambda: regenerate(restarted, alice, thread.id)):
        with pytest.raises(ChatError, match="provider_outcome_unknown"):
            operation()


@pytest.mark.parametrize("state", ["pending", "streaming"])
def test_active_request_blocks_branch_change(chat_env, state):
    service, alice, _, _ = chat_env
    thread, _, _ = prepare(service, alice)
    pending = request(service, alice, thread.id, "Active suffix")
    if state == "streaming":
        events = iter(service.stream_events(alice.bearer, pending.id))
        assert "message.start" in next(events)
    source = graph_page(service, alice.bearer, thread.id).turns[0].id
    before = durable_rows(service)
    for operation in (lambda: edit(service, alice, thread.id, "Edit prefix", source),
                      lambda: switch(service, alice, thread.id, thread.id)):
        with pytest.raises(ChatError, match="active_request_exists"):
            operation()
    assert durable_rows(service) == before


def test_image_edit_preserves_ordered_snapshots(vision_env):
    service, alice, _, _, objects = vision_env
    images = [asset(service, alice, objects, value) for value in (b"a", b"bb")]
    thread = new_thread(service, alice)
    image_only = submit(service, alice, thread, images)
    finish(service, alice, image_only)
    before = durable_rows(service)
    with pytest.raises(ChatError, match="message_unchanged"):
        edit(service, alice, thread.id, " \u0085 ")
    assert durable_rows(service) == before
    captioned, _, _ = edit(service, alice, thread.id, "Caption")
    finish(service, alice, captioned.request)
    cleared, _, _ = edit(service, alice, thread.id, "\x1c\u0085")
    turn = graph_page(service, alice.bearer, thread.id).turns[-1]
    assert turn.user_message.content == "" and [item.asset_id for item in turn.user_message.attachments] == images
    with service.engine.begin() as conn:
        original = conn.execute(sa.select(t.attachments).where(t.attachments.c.request_id == image_only.id)
            .order_by(t.attachments.c.ordinal)).mappings().all()
        assert original and all(dict(row) in before[t.attachments.name] for row in original)
    finish(service, alice, cleared.request)


@pytest.mark.parametrize("boundary,code", [("vision", "model_vision_unsupported"),
    ("credential", "credential_not_verified"), ("asset", "attachment_not_found")])
def test_none_source_revalidates_admission(vision_env, monkeypatch, boundary, code):
    service, alice, bob, _, objects = vision_env
    image = asset(service, alice, objects)
    thread = new_thread(service, alice)
    stopped = submit(service, alice, thread, [image], text="Original")
    service.stop(alice.bearer, alice.view.csrf_token, stopped.id)
    assert graph_page(service, alice.bearer, thread.id).turns[0].selected_attempt_id is None
    table = t.connections if boundary == "credential" else t.media_assets
    column = "enabled" if boundary == "credential" else "account_id"
    value = False if boundary == "credential" else bob.view.account.id
    if boundary != "vision":
        with service.engine.begin() as conn:
            conn.execute(sa.update(table).values({column: value}))
    before = durable_rows(service)
    with monkeypatch.context() as patch:
        if boundary == "vision":
            patch.setattr(service, "static_vision_supported", lambda *_: False)
        with pytest.raises(ChatError, match=code):
            edit(service, alice, thread.id, "Revised")
    assert durable_rows(service) == before
    if boundary != "vision":
        with service.engine.begin() as conn:
            conn.execute(sa.update(table).values({column: True if boundary == "credential" else alice.view.account.id}))
    accepted, _, _ = edit(service, alice, thread.id, "Revised")
    assert accepted.request.model == stopped.model
