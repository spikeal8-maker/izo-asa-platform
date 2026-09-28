"""Private image admission, replay and provider context without external calls."""
import base64
import hashlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.chat import tables as chat
from izo.chat.catalog import OpenRouterCatalogCache
from izo.chat.provider_openrouter import FakeOpenRouterProvider
from izo.chat.provider import ProviderFailure
from izo.chat.execution import FakeDeepSeekProvider
from izo.chat.schemas import OpenRouterCatalogModel
from izo.chat.schemas import MAX_CHAT_IMAGE_BYTES, RequestCreate
from izo.chat.service import ChatError, ChatService
from test_chat import chat_env, connect_key, new_thread
from test_chat_multi_provider import _connect_openrouter


class Objects:
    def __init__(self):
        self.values = {}

    def read(self, key, maximum):
        data = self.values[key]
        assert len(data) <= maximum
        return data


def asset(service, owner, objects, data=b"normalized-private-png", *, size=None):
    asset_id = uuid4()
    key = "test/" + str(asset_id)
    objects.values[key] = data
    with service.engine.begin() as conn:
        conn.execute(sa.insert(chat.media_assets).values(
            id=asset_id, account_id=owner.view.account.id,
            object_key=key, sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data) if size is None else size,
            width=8, height=8, created_at=service.now()))
    return asset_id


@pytest.fixture
def vision_env(chat_env):
    service, alice, bob, clock = chat_env
    chat.media_assets.create(service.engine, checkfirst=True)
    objects = Objects()
    service.media_store = objects
    connect_key(service, alice)
    return service, alice, bob, clock, objects


def submit(service, owner, thread, ids, *, text="", model="deepseek-flash", request_id=None):
    return service.create_request(
        owner.bearer, owner.view.csrf_token, thread.id,
        RequestCreate(request_id=request_id or uuid4(), text=text,
                      model=model, attachment_ids=ids))


def context(service, owner, request_id):
    with service.engine.begin() as conn:
        row = conn.execute(sa.select(chat.requests).where(
            chat.requests.c.id == request_id)).mappings().one()
    return service._context_and_key(owner.view.account.id, row)[-1]


def test_schema_image_only_and_duplicate_bounds():
    uid = uuid4()
    assert RequestCreate(request_id=uid, text="", model="deepseek-flash",
                         attachment_ids=[uid]).text == ""
    with pytest.raises(ValidationError):
        RequestCreate(request_id=uid, text="   ", model="deepseek-flash")
    with pytest.raises(ValidationError):
        RequestCreate(request_id=uid, text="x", model="deepseek-flash",
                      attachment_ids=[uid, uid])
    with pytest.raises(ValidationError):
        RequestCreate(request_id=uid, text="x", model="deepseek-flash",
                      attachment_ids=[uuid4() for _ in range(6)])


def test_image_only_ordered_context_and_exact_replay(vision_env):
    service, alice, _, _, objects = vision_env
    published = service.public_policy(alice.bearer)
    flash = next(item for item in published.models if item.id == "deepseek-flash")
    assert flash.vision == service.static_vision_supported(flash.id, flash.provider)
    assert not service.static_vision_supported("deepseek-v4-pro", "deepseek")
    first = asset(service, alice, objects, b"a")
    second = asset(service, alice, objects, b"bb")
    thread = new_thread(service, alice)
    stable = uuid4()
    sent = submit(service, alice, thread, [second, first], request_id=stable)
    replay = submit(service, alice, thread, [second, first], request_id=stable)
    assert replay.id == sent.id
    with pytest.raises(ChatError, match="request_conflict"):
        submit(service, alice, thread, [first, second], request_id=stable)
    detail = service.thread_detail(alice.bearer, thread.id)
    assert detail.thread.title == "Изображение"
    assert [item.asset_id for item in detail.messages[0].attachments] == [second, first]
    assert detail.messages[1].attachments == []
    messages = context(service, alice, stable)
    assert messages[0]["role"] == "system"
    parts = messages[-1]["content"]
    assert parts[0] == {"type": "text", "text": ""}
    assert [base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
            for part in parts[1:]] == [b"bb", b"a"]


def test_cross_account_missing_unsupported_and_size(vision_env):
    service, alice, bob, _, objects = vision_env
    foreign = asset(service, bob, objects)
    thread = new_thread(service, alice)
    with pytest.raises(ChatError, match="attachment_not_found"):
        submit(service, alice, thread, [foreign])
    with pytest.raises(ChatError, match="attachment_not_found"):
        submit(service, alice, thread, [uuid4()])
    own = asset(service, alice, objects)
    with pytest.raises(ChatError, match="model_vision_unsupported"):
        submit(service, alice, thread, [own], model="openrouter-auto")
    huge = asset(service, alice, objects, size=MAX_CHAT_IMAGE_BYTES + 1)
    with pytest.raises(ChatError, match="image_too_large"):
        submit(service, alice, thread, [huge])
    large = [asset(service, alice, objects, size=MAX_CHAT_IMAGE_BYTES)
             for _ in range(3)]
    with pytest.raises(ChatError, match="image_context_too_large"):
        submit(service, alice, thread, large)


def test_unavailable_and_corrupt_object_fail_before_provider_call(vision_env):
    service, alice, _, _, objects = vision_env
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    sent = submit(service, alice, thread, [uid])
    key = next(iter(objects.values))
    objects.values[key] = b"different"
    with pytest.raises(ChatError, match="attachment_integrity_error"):
        context(service, alice, sent.id)
    del objects.values[key]
    with pytest.raises(ChatError, match="attachment_unavailable"):
        context(service, alice, sent.id)


def test_followup_includes_prior_image_without_catalog_resolution(vision_env):
    service, alice, _, _, objects = vision_env
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    first = submit(service, alice, thread, [uid], text="Что здесь?")
    list(service.stream_events(alice.bearer, first.id))
    second = submit(service, alice, thread, [], text="Расскажи подробнее")
    messages = context(service, alice, second.id)
    assert any(isinstance(item["content"], list) for item in messages)
    assert messages[-1]["content"] == "Расскажи подробнее"


def test_openrouter_vision_admission_snapshot_survives_catalog_outage(vision_env):
    service, alice, _, _, objects = vision_env
    service.providers["openrouter"] = FakeOpenRouterProvider()
    _connect_openrouter(service, alice)
    models = [OpenRouterCatalogModel(
        id="vendor/vision", name="Vision", provider="vendor",
        context_length=32768, vision=True),
        OpenRouterCatalogModel(
            id="vendor/text", name="Text", provider="vendor",
            context_length=32768, vision=False)]
    service._openrouter_catalog = OpenRouterCatalogCache(
        clock=service.clock, fetcher=lambda: models)
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    with pytest.raises(ChatError, match="model_vision_unsupported"):
        submit(service, alice, thread, [uid], model="vendor/text")
    stable = uuid4()
    sent = submit(service, alice, thread, [uid], model="vendor/vision",
                  request_id=stable)
    service._openrouter_catalog.get = lambda: (_ for _ in ()).throw(
        AssertionError("Catalog must not be fetched for admitted execution/replay"))
    assert submit(service, alice, thread, [uid], model="vendor/vision",
                  request_id=stable).id == sent.id
    assert isinstance(context(service, alice, stable)[-1]["content"], list)


def test_openrouter_image_unknown_paid_outcome_blocks_new_request(vision_env):
    service, alice, _, _, objects = vision_env
    service.providers["openrouter"] = FakeOpenRouterProvider()
    _connect_openrouter(service, alice)
    service._openrouter_catalog = OpenRouterCatalogCache(
        clock=service.clock, fetcher=lambda: [OpenRouterCatalogModel(
            id="vendor/vision", name="Vision", provider="vendor",
            context_length=32768, vision=True)])
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    sent = submit(service, alice, thread, [uid], model="vendor/vision")
    service.providers["openrouter"].stream = lambda *args: (
        _ for _ in ()).throw(ProviderFailure("provider_unavailable"))
    assert "provider_outcome_unknown" in "".join(
        service.stream_events(alice.bearer, sent.id))
    with pytest.raises(ChatError, match="provider_outcome_unknown"):
        submit(service, alice, thread, [uid], model="vendor/vision")
    assert submit(service, alice, thread, [uid], model="vendor/vision",
                  request_id=sent.id).id == sent.id


def test_missing_image_fails_before_openrouter_paid_marker(vision_env):
    service, alice, _, _, objects = vision_env
    service.providers["openrouter"] = FakeOpenRouterProvider()
    _connect_openrouter(service, alice)
    service._openrouter_catalog = OpenRouterCatalogCache(
        clock=service.clock, fetcher=lambda: [OpenRouterCatalogModel(
            id="vendor/vision", name="Vision", provider="vendor",
            context_length=32768, vision=True)])
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    sent = submit(service, alice, thread, [uid], model="vendor/vision")
    objects.values.clear()
    events = "".join(service.stream_events(alice.bearer, sent.id))
    assert "attachment_unavailable" in events
    assert service.request(alice.bearer, sent.id).error_code == "attachment_unavailable"
    assert "provider_outcome_unknown" not in events
    submit(service, alice, thread, [], text="try text", model="vendor/vision")


def test_deepseek_image_unknown_outcome_blocks_retry_and_stop(vision_env):
    service, alice, _, _, objects = vision_env
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    sent = submit(service, alice, thread, [uid])
    class InterruptedProvider:
        def stream(self, *args):
            yield "partial"
            raise ProviderFailure("provider_stream_interrupted")
    service.provider = InterruptedProvider()
    events = "".join(service.stream_events(alice.bearer, sent.id))
    assert "partial" in events and "provider_outcome_unknown" in events
    with pytest.raises(ChatError, match="provider_outcome_unknown"):
        submit(service, alice, thread, [], text="again")
    assert submit(service, alice, thread, [uid], request_id=sent.id).id == sent.id

    second = new_thread(service, alice)
    started = submit(service, alice, second, [uid])
    stream = service.stream_events(alice.bearer, started.id)
    assert "message.start" in next(stream)
    assert "partial" in next(stream)
    service.stop(alice.bearer, alice.view.csrf_token, started.id)
    assert "message.interrupted" in "".join(stream)
    assert service.request(alice.bearer, started.id).error_code == "provider_outcome_unknown"
    with pytest.raises(ChatError, match="provider_outcome_unknown"):
        submit(service, alice, second, [], text="blind retry")


def test_deepseek_image_restart_preserves_paid_barrier(vision_env):
    service, alice, _, _, objects = vision_env
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    sent = submit(service, alice, thread, [uid])
    with service.engine.begin() as conn:
        conn.execute(sa.update(chat.requests).where(chat.requests.c.id == sent.id)
                     .values(state="streaming"))
    service._mark_paid_submission(sent.id)
    recovered = ChatService(service.auth, service.policy, FakeDeepSeekProvider(),
                            clock=service.clock, media_store=objects)
    assert recovered.request(alice.bearer, sent.id).error_code == "provider_outcome_unknown"
    with pytest.raises(ChatError, match="provider_outcome_unknown"):
        submit(recovered, alice, thread, [], text="restart retry")
