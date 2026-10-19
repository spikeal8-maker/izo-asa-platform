"""Graph commands share the existing session, origin, CSRF and owned Chat API."""
from uuid import uuid4

import pytest

from test_chat_graph_requests import RecordingProvider
from test_chat_http import ORIGIN, http_env, save_and_verify, signup

BASE = "/api/v1/chat"


def completed_thread(client, text="Секретный вопрос"):
    thread = client.post(f"{BASE}/threads", json={"title": None})
    assert thread.status_code == 201
    path = f"{BASE}/threads/{thread.json()['id']}"
    sent = client.post(f"{path}/requests", json={
        "request_id": str(uuid4()), "text": text, "model": "deepseek-flash"})
    assert sent.status_code == 202
    stream = client.get(f"{BASE}/requests/{sent.json()['id']}/events")
    assert stream.status_code == 200 and "event: message.done" in stream.text
    graph = client.get(f"{path}/graph")
    assert graph.status_code == 200
    return path, graph.json()


def commands(graph):
    turn = graph["turns"][0]
    shared = {"branch_id": graph["active_branch_id"], "expected_revision": graph["revision"]}
    return (turn, {**shared, "request_id": str(uuid4()),
                  "source_attempt_id": turn["selected_attempt_id"]},
            {**shared, "attempt_id": turn["selected_attempt_id"]})


def test_http_regenerate_stream_select_reload_and_physical_history(http_env):
    _, service, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    service.provider = RecordingProvider()
    path, graph = completed_thread(client)
    original = client.get(path).json()
    assert original["graph_version"] == 1
    turn, command, selection = commands(graph)
    endpoint = f"{path}/turns/{turn['id']}"
    accepted = client.post(f"{endpoint}/regenerate", json=command)
    assert accepted.status_code == 202, accepted.text
    result = accepted.json()
    assert result["request"]["id"] == command["request_id"]
    assert result["turn"]["selected_attempt_id"] == turn["selected_attempt_id"]
    assert result["revision"] > graph["revision"]
    assert result["turn"]["latest_attempt"]["state"] == "pending"
    assert "event: message.done" in client.get(
        f"{BASE}/requests/{command['request_id']}/events").text
    variants = client.get(f"{endpoint}/attempts")
    assert variants.status_code == 200
    fresh = variants.json()
    assert [attempt["ordinal"] for attempt in fresh["attempts"]] == [1, 2]
    assert fresh["turn"]["completed_count"] == fresh["turn"]["selected_completed_position"] == 2
    stale = client.patch(f"{endpoint}/selection", json=selection)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "graph_revision_conflict"
    switched = client.patch(f"{endpoint}/selection", json={
        **selection, "expected_revision": fresh["revision"]})
    assert switched.status_code == 200
    reloaded = client.get(f"{path}/graph").json()
    assert reloaded["revision"] == switched.json()["revision"]
    assert reloaded["turns"][0]["selected_attempt_id"] == turn["selected_attempt_id"]
    physical = client.get(path).json()
    assert physical["messages"][:2] == original["messages"]
    assert [message["sequence"] for message in physical["messages"]] == [1, 2, 3]
    assert client.get(f"{path}/messages?before_sequence=3").json()["messages"] == original["messages"]
    replay = client.post(f"{endpoint}/regenerate", json=command)
    assert replay.status_code == 202 and replay.json()["request"]["state"] == "completed"
    assert len(service.provider.calls) == 2
    for private in ("connection_id", "credential_generation", "ciphertext", "fingerprint", "snapshot", "object_key"):
        assert private not in accepted.text + variants.text + switched.text


@pytest.mark.parametrize("mutation", ["regenerate", "selection"])
@pytest.mark.parametrize("boundary", ["origin", "csrf", "session"])
def test_mutations_require_origin_csrf_and_live_session(http_env, mutation, boundary):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    path, graph = completed_thread(client)
    turn, regenerate, selection = commands(graph)
    endpoint = f"{path}/turns/{turn['id']}/{mutation}"
    headers = {"Origin": "https://foreign.invalid"} if boundary == "origin" else {}
    if boundary == "csrf":
        client.headers.pop("X-CSRF-Token")
    if boundary == "session":
        client.cookies.clear()
    response = client.request("POST" if mutation == "regenerate" else "PATCH", endpoint,
        json=regenerate if mutation == "regenerate" else selection, headers=headers)
    assert response.status_code == (401 if boundary == "session" else 403), response.text
    if boundary != "session":
        assert client.get(f"{path}/graph").json()["revision"] == graph["revision"]


def test_foreign_thread_turn_attempt_and_request_are_hidden(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    alice_path, alice_graph = completed_thread(client)
    alice_turn, regenerate, selection = commands(alice_graph)
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token")
    signup(None, client, "bob@example.invalid")
    save_and_verify(client)
    assert client.get(f"{alice_path}/graph").status_code == 404
    foreign = f"{alice_path}/turns/{alice_turn['id']}"
    assert client.get(f"{foreign}/attempts").status_code == 404
    assert client.post(f"{foreign}/regenerate", json=regenerate).status_code == 404
    assert client.patch(f"{foreign}/selection", json=selection).status_code == 404
    bob_path, bob_graph = completed_thread(client, "Свой вопрос")
    bob_turn, bob_regen, bob_select = commands(bob_graph)
    own = f"{bob_path}/turns/{bob_turn['id']}"
    assert client.get(f"{bob_path}/turns/{alice_turn['id']}/attempts").status_code == 404
    assert client.post(f"{own}/regenerate", json={
        **bob_regen, "source_attempt_id": alice_turn["selected_attempt_id"]}).status_code == 404
    assert client.patch(f"{own}/selection", json={
        **bob_select, "attempt_id": alice_turn["selected_attempt_id"]}).status_code == 404
    stolen_id = {**bob_regen, "request_id": alice_turn["selected_attempt_id"]}
    assert client.post(f"{own}/regenerate", json=stolen_id).status_code == 404
    client.cookies.clear()
    assert client.get(f"{bob_path}/graph").status_code == 401
    assert client.get(f"{own}/attempts").status_code == 401


@pytest.mark.parametrize("invalid", [0, -1, 9223372036854775808, "not-a-number"])
def test_graph_cursors_are_exclusive_positive_int64(http_env, invalid):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    path, graph = completed_thread(client)
    turn = graph["turns"][0]
    for endpoint, name in ((f"{path}/graph", "before_turn_sequence"),
                           (f"{path}/turns/{turn['id']}/attempts", "before_ordinal")):
        rejected = client.get(endpoint, params={name: invalid})
        assert rejected.status_code == 422 and rejected.json() == {"error": {"code": "invalid_input"}}
        page = client.get(endpoint, params={name: 1})
        assert page.status_code == 200 and page.json().get("turns", page.json().get("attempts")) == []


def test_commands_reject_extra_authority_fields_bad_ids_and_conflicting_intent(http_env):
    _, _, client = http_env
    signup(None, client, "alice@example.invalid")
    save_and_verify(client)
    path, graph = completed_thread(client)
    turn, regenerate, selection = commands(graph)
    endpoint = f"{path}/turns/{turn['id']}"
    for mutation, command, method in (("regenerate", regenerate, "POST"), ("selection", selection, "PATCH")):
        for invalid in ({**command, "account_id": str(uuid4())}, {**command, "expected_revision": -1},
                        {**command, "branch_id": "malformed"}, {**command, "expected_revision": 9223372036854775808}):
            response = client.request(method, f"{endpoint}/{mutation}", json=invalid)
            assert response.status_code == 422 and response.json() == {"error": {"code": "invalid_input"}}
    accepted = client.post(f"{endpoint}/regenerate", json=regenerate)
    assert accepted.status_code == 202
    pending = client.patch(f"{endpoint}/selection", json={**selection,
        "attempt_id": regenerate["request_id"], "expected_revision": accepted.json()["revision"]})
    assert pending.status_code == 409 and pending.json()["error"]["code"] == "attempt_not_completed"
    conflict = client.post(f"{endpoint}/regenerate", json={
        **regenerate, "source_attempt_id": regenerate["request_id"]})
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "request_conflict"
    body_limit = client.post(f"{endpoint}/regenerate", content=b"x" * 32769,
        headers={"Content-Type": "application/json", "Origin": ORIGIN})
    assert body_limit.status_code == 413


class PGGateProvider(RecordingProvider):
    """Opt-in PostgreSQL runner synchronization, never installed by production."""
    def __init__(self):
        from threading import Event
        super().__init__()
        self.entered, self.release = Event(), Event()

    def stream(self, key, model, messages, max_tokens, timeout, stop):
        self.verify(key)
        self.calls.append(messages)
        self.entered.set()
        yield "Durable PostgreSQL answer"
        assert self.release.wait(20), "PG provider gate timed out"


def pg_wait_blocked(service, count):
    import time
    from threading import Event
    import sqlalchemy as sa
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with service.engine.connect() as conn:
            rows = conn.execute(sa.text("SELECT query FROM pg_stat_activity "
                "WHERE application_name=:label AND cardinality(pg_blocking_pids(pid)) > 0"),
                {"label": service._graph_pg_label}).scalars().all()
        if len(rows) >= count and any("chat_threads" in query for query in rows):
            return
        Event().wait(0.01)
    raise AssertionError("PostgreSQL did not observe the expected real Thread lock contenders")


def pg_parallel(service, thread_id, operations):
    from concurrent.futures import ThreadPoolExecutor
    import sqlalchemy as sa
    from izo.chat import tables as t
    from izo.chat.service import ChatError

    def run(operation):
        try:
            return operation()
        except ChatError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        with service.engine.begin() as holder:
            holder.execute(sa.select(t.threads.c.id).where(
                t.threads.c.id == thread_id).with_for_update())
            futures = [pool.submit(run, operation) for operation in operations]
            pg_wait_blocked(service, len(operations))
        return [future.result(timeout=15) for future in futures]


def pg_bootstrap_catalog(engine):
    """PostgreSQL gets the real Alembic seed; runtime deliberately never seeds it."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from izo.accounts import tables as accounts
    from test_chat_graph_migration import migration
    catalog_tables = {"catalog_state", "catalog_models", "catalog_events"}
    accounts.metadata.create_all(engine, tables=[table for table in accounts.metadata.sorted_tables
        if table.name not in catalog_tables])
    with engine.begin() as conn:
        seeded = migration("0013_admin_catalog")
        seeded.op = Operations(MigrationContext.configure(conn))
        seeded.upgrade()
