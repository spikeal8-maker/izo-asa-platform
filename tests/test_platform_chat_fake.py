"""P0-B2/C synthetic vertical: own Accounts/Graph/SSE, no paid provider."""
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from izo.chat import tables as chat
from izo.chat.credential_crypto import encrypt
from izo.chat.provider import ProviderFailure
from izo.platform_providers import tables as platform
from izo.platform_providers.namespace import AAD_PROVIDER, PLATFORM_ID, PLATFORM_NAMESPACE
from test_chat_http import http_env, signup

MODEL = "platform:deepseek-flash"
CHAT = "/api/v1/chat"
KEY = "x" * 32


@pytest.fixture
def platform_http(http_env):
    auth, service, client = http_env
    service.platform_demo = True
    platform.metadata.create_all(service.engine)
    nonce, ciphertext = encrypt(
        service.policy.root_key_bytes(), PLATFORM_NAMESPACE, PLATFORM_ID,
        1, KEY, AAD_PROVIDER)
    now = service.now()
    with service.engine.begin() as conn:
        conn.execute(sa.insert(platform.connections).values(
            provider="deepseek", nonce=nonce, ciphertext=ciphertext,
            model="deepseek-flash", generation=1, revision=1,
            enabled=True, verified_at=now, daily_limit=3,
            concurrency_limit=1, last_operation_id=uuid4(),
            last_operation_hash="0" * 64, created_at=now, updated_at=now))
    return service, client


def thread(client):
    result = client.post(CHAT + "/threads", json={"title": None})
    assert result.status_code == 201, result.text
    return result.json()["id"]


def send(client, tid, message="Test message", rid=None):
    rid = str(rid or uuid4())
    body = {"request_id": rid, "text": message, "model": MODEL}
    result = client.post(f"{CHAT}/threads/{tid}/requests", json=body)
    return result, body


def stream(client, rid):
    result = client.get(f"{CHAT}/requests/{rid}/events")
    assert result.status_code == 200
    return result.text


def usage(service):
    with service.engine.begin() as conn:
        row = conn.execute(sa.select(platform.daily_usage)).mappings().first()
        return row["requests_admitted"] if row else 0


def test_platform_model_user_has_no_key_and_graph_stream_is_durable(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    credentials = client.get(CHAT + "/credentials")
    assert credentials.status_code == 200
    assert all(not x["configured"] for x in credentials.json()["credentials"])
    policy = client.get(CHAT + "/policy")
    assert policy.status_code == 200
    assert policy.json()["default_model"] == MODEL
    assert any(x["id"] == MODEL and x["provider"] == "platform"
               for x in policy.json()["models"])
    tid = thread(client)
    first, body = send(client, tid, "Какая модель отвечает?")
    assert first.status_code == 202, first.text
    repeated = client.post(f"{CHAT}/threads/{tid}/requests", json=body)
    assert repeated.status_code == 202 and repeated.json()["id"] == body["request_id"]
    assert usage(service) == 1
    events = stream(client, body["request_id"])
    assert "event: message.done" in events
    detail = client.get(f"{CHAT}/threads/{tid}")
    assert detail.status_code == 200
    assert "Ответ DeepSeek test:" in detail.text
    assert KEY not in detail.text
    graph = client.get(f"{CHAT}/threads/{tid}/graph")
    assert graph.status_code == 200
    assert len(graph.json()["turns"]) == 1
    assert graph.json()["turns"][0]["latest_attempt"]["state"] == "completed"
    assert not any(word in graph.text for word in ("ciphertext", "nonce", "connection_id"))
    signup(None, client, "bob@example.invalid")
    assert client.get(f"{CHAT}/threads/{tid}").status_code == 404
    assert client.get(f"{CHAT}/threads/{tid}/graph").status_code == 404


def test_pending_global_concurrency_and_daily_limit_atomic(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    t1, t2 = thread(client), thread(client)
    first, command = send(client, t1, "First pending")
    assert first.status_code == 202, first.text
    blocked, _ = send(client, t2, "Should not admit while pending")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "platform_concurrency_limit"
    assert usage(service) == 1
    assert "event: message.done" in stream(client, command["request_id"])
    second, command2 = send(client, t2, "Second after release")
    assert second.status_code == 202, second.text
    assert "event: message.done" in stream(client, command2["request_id"])
    third, command3 = send(client, t2, "Third after second")
    assert third.status_code == 202, third.text
    assert "event: message.done" in stream(client, command3["request_id"])
    assert usage(service) == 3
    denied, _ = send(client, t1, "Fourth over daily quota")
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "platform_daily_limit"
    assert usage(service) == 3
    old_replay = client.post(f"{CHAT}/threads/{t1}/requests", json=command)
    assert old_replay.status_code == 202
    assert usage(service) == 3
    mismatch = client.post(f"{CHAT}/threads/{t1}/requests",
                           json={**command, "text": "Different intent"})
    assert mismatch.status_code == 409
    assert usage(service) == 3


def test_disabled_rotation_and_old_history_stay_isolated(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    tid = thread(client)
    first, body = send(client, tid)
    assert first.status_code == 202
    assert "event: message.done" in stream(client, body["request_id"])
    with service.engine.begin() as conn:
        conn.execute(sa.update(platform.connections).values(enabled=False))
    assert not any(x["provider"] == "platform" for x in client.get(CHAT + "/policy").json()["models"])
    denied, _ = send(client, tid, "Disabled provider")
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "platform_model_unavailable"
    assert "Ответ DeepSeek test:" in client.get(f"{CHAT}/threads/{tid}").text
    with service.engine.begin() as conn:
        conn.execute(sa.update(platform.connections).values(
            enabled=True, verified_at=None, generation=2, revision=2))
    assert not any(x["provider"] == "platform" for x in client.get(CHAT + "/policy").json()["models"])
    assert usage(service) == 1


def test_unknown_outcome_never_replays_or_reissues(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    tid = thread(client)
    first, command = send(client, tid, "Uncertain attempt")
    assert first.status_code == 202
    class UncertainFake:
        calls = 0
        def stream(self, key, model, messages, max_tokens, timeout, stop):
            self.calls += 1
            assert key == KEY
            raise ProviderFailure("provider_stream_interrupted")
            yield "never"

    source = UncertainFake()
    service.provider = source
    event = stream(client, command["request_id"])
    assert "message.error" in event or "message.interrupted" in event
    assert source.calls == 1
    replay = client.post(f"{CHAT}/threads/{tid}/requests", json=command)
    assert replay.status_code == 202
    assert source.calls == 1
    follow = stream(client, command["request_id"])
    assert "message." in follow
    assert source.calls == 1
    with service.engine.begin() as conn:
        original = conn.execute(sa.select(chat.requests).where(
            chat.requests.c.id == UUID(command["request_id"]))).mappings().one()
        assert original["state"] in ("error", "interrupted")
        assert original["error_code"] == "provider_outcome_unknown"
    stopped, _ = send(client, tid, "Must not post after unknown outcome")
    assert stopped.status_code == 409
    assert stopped.json()["error"]["code"] == "provider_outcome_unknown"


def test_original_byok_still_operates_after_platform_integration(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    from test_chat_http import save_and_verify
    verified = save_and_verify(client)
    assert verified["verified"]
    response = client.get(CHAT + "/credentials")
    assert response.status_code == 200
    personal = [row for row in response.json()["credentials"]
                if row["provider"] == "deepseek"]
    assert len(personal) == 1 and personal[0]["verified"]
    tid = thread(client)
    data = {"request_id": str(uuid4()), "text": "Personal existing BYOK",
            "model": "deepseek-flash"}
    request = client.post(f"{CHAT}/threads/{tid}/requests", json=data)
    assert request.status_code == 202
    assert "event: message.done" in stream(client, data["request_id"])
    with service.engine.begin() as conn:
        providers = set(conn.execute(sa.select(chat.connections.c.provider)).scalars())
        assert "deepseek" in providers
        assert usage(service) == 0  # Personal BYOK does not spend shared quota.


def test_platform_flag_absent_is_fail_closed(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    service.platform_demo = False
    assert not any(row["provider"] == "platform"
                   for row in client.get(CHAT + "/policy").json()["models"])
    tid = thread(client)
    denied, _ = send(client, tid, "Must not admit without isolated flag")
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "model_not_allowed"
    assert usage(service) == 0


def test_key_rotation_invalidates_pending_shadow_before_execution(platform_http):
    service, client = platform_http
    signup(None, client, "alice@example.invalid")
    tid = thread(client)
    pending, command = send(client, tid, "Pending before rotation")
    assert pending.status_code == 202
    root = service.policy.root_key_bytes()
    new_nonce, new_cipher = encrypt(
        root, PLATFORM_NAMESPACE, PLATFORM_ID, 2, KEY, AAD_PROVIDER)
    with service.engine.begin() as conn:
        conn.execute(sa.update(platform.connections).values(
            nonce=new_nonce, ciphertext=new_cipher,
            generation=2, revision=2, verified_at=service.now(), enabled=True))
    result = stream(client, command["request_id"])
    assert "message.error" in result
    original = client.get(f"{CHAT}/requests/{command['request_id']}")
    assert original.status_code == 200
    assert original.json()["state"] == "error"
    assert "Ответ DeepSeek test:" not in result
    # Rotation does not retroactively claim that old pending inference completed.
    assert usage(service) == 1
