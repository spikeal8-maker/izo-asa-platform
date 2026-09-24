"""Focused durable Chat vision tests."""
import hashlib
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.chat import tables as chat
from izo.chat.credentials import ChatError
from test_chat import chat_env, connect_key, request


def media_asset(service, receipt, data=b"\x89PNG\r\n\x1a\nsynthetic-chat-image"):
    asset_id = uuid4()
    key = f"assets/{receipt.view.account.id.hex}/{asset_id.hex}/image.png"
    service.media_store.objects[key] = data
    with service.engine.begin() as conn:
        conn.execute(sa.insert(chat.media_assets).values(
            id=asset_id, account_id=receipt.view.account.id, object_key=key,
            sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data),
            width=16, height=16, created_at=service.now()))
    return asset_id


def test_image_attachment_persists_and_flash_reuses_it_for_followup(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    asset_id = media_asset(service, alice)
    first = request(service, alice, thread.id, "Что изображено?",
                    attachment_ids=[asset_id])
    assert "message.done" in "".join(service.stream_events(alice.bearer, first.id))

    detail = service.thread_detail(alice.bearer, thread.id)
    user = detail.messages[0]
    assert user.content == "Что изображено?"
    assert len(user.attachments) == 1
    assert user.attachments[0].asset_id == asset_id
    assert user.attachments[0].media_type == "image/png"
    assert "base64" not in user.content and "data:image" not in user.content

    followup = request(service, alice, thread.id, "Какого цвета предмет слева?")
    assert "message.done" in "".join(service.stream_events(alice.bearer, followup.id))
    reloaded = service.thread_detail(alice.bearer, thread.id)
    assert "Изображения в контексте: 1" in reloaded.messages[-1].content
    assert reloaded.messages[0].attachments[0].asset_id == asset_id


def test_pro_model_rejects_image_and_cross_owner_asset_is_hidden(chat_env):
    service, alice, bob, _ = chat_env
    connect_key(service, alice)
    connect_key(service, bob)
    alice_asset = media_asset(service, alice)
    alice_thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    with pytest.raises(ChatError, match="model_vision_unsupported"):
        request(service, alice, alice_thread.id, "Посмотри",
                model="deepseek-v4-pro", attachment_ids=[alice_asset])

    bob_thread = service.create_thread(bob.bearer, bob.view.csrf_token, None)
    with pytest.raises(ChatError, match="attachment_not_found"):
        request(service, bob, bob_thread.id, "Укради вложение",
                attachment_ids=[alice_asset])

def test_provider_wire_multimodal_contract_preserves_image_parts():
    import io
    import json
    from threading import Event
    from types import SimpleNamespace
    from izo.chat.provider import DeepSeekProvider

    image_url = "data:image/png;base64,iVBORw0KGgo="
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "Что изображено?"},
        {"type": "image_url", "image_url": {"url": image_url, "detail": "auto"}},
    ]}]

    def open_response(outbound, timeout):
        body = json.loads(outbound.data)
        assert body["model"] == "deepseek-flash"
        assert body["messages"] == messages
        response = io.BytesIO(
            b'data: {"choices":[{"delta":{"content":"vision-ok"},"finish_reason":"stop"}]}\n\n'
            b'data: [DONE]\n\n')
        response.status = 200
        return response

    provider = DeepSeekProvider()
    provider.opener = SimpleNamespace(open=open_response)
    result = "".join(provider.stream(
        "x" * 32, "deepseek-flash", messages, 2048, 75, Event()))
    assert result == "vision-ok"


def test_five_images_preserve_db_and_provider_order(chat_env):
    import base64
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(alice.bearer, alice.view.csrf_token, None)
    payloads = [
        b"\x89PNG\r\n\x1a\nordered-" + str(index).encode()
        for index in range(5)
    ]
    asset_ids = [media_asset(service, alice, data) for data in payloads]
    created = request(
        service, alice, thread.id, "Проверь порядок",
        attachment_ids=asset_ids,
    )
    with service.engine.begin() as conn:
        request_row = conn.execute(sa.select(chat.requests).where(
            chat.requests.c.id == created.id)).mappings().one()
    _, provider_messages = service._context_and_key(
        alice.view.account.id, request_row)
    parts = provider_messages[-1]["content"]
    assert [part["type"] for part in parts] == [
        "text", "image_url", "image_url", "image_url", "image_url", "image_url"]
    encoded = [
        part["image_url"]["url"].split(",", 1)[1]
        for part in parts[1:]
    ]
    assert [base64.b64decode(item) for item in encoded] == payloads
    detail = service.thread_detail(alice.bearer, thread.id)
    assert [item.asset_id for item in detail.messages[0].attachments] == asset_ids


def test_six_images_and_duplicate_ids_are_rejected_by_request_schema():
    from pydantic import ValidationError
    from izo.chat.schemas import RequestCreate

    ids = [uuid4() for _ in range(6)]
    with pytest.raises(ValidationError):
        RequestCreate(
            request_id=uuid4(), text="too many",
            model="deepseek-flash", attachment_ids=ids)
    duplicate = uuid4()
    with pytest.raises(ValidationError):
        RequestCreate(
            request_id=uuid4(), text="duplicate",
            model="deepseek-flash", attachment_ids=[duplicate, duplicate])
