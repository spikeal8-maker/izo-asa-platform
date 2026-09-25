"""CHAT-MULTI-PROVIDER-001 focused provider/credential/request regressions."""
from __future__ import annotations

import io
import importlib.util
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from urllib.error import HTTPError
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.exceptions import InvalidTag

from izo.chat import tables as chat
from izo.chat.credentials import (
    ChatError, decrypt, encrypt,
)
from izo.chat.provider import ProviderFailure
from izo.chat.provider_openrouter import (
    FakeOpenRouterProvider, OpenRouterProvider,
)
from izo.chat.schemas import (
    CREDENTIAL_WINDOW_LIMIT, CredentialCommand, CredentialWrite,
)
from test_chat import KEY, chat_env, connect_key, request

ROOT = Path(__file__).resolve().parents[1]
OPENROUTER_KEY = FakeOpenRouterProvider.TEST_KEY


def connect_openrouter(service, receipt):
    service.providers["openrouter"] = FakeOpenRouterProvider()
    saved = service.save_credential(
        receipt.bearer, receipt.view.csrf_token,
        CredentialWrite(operation_id=uuid4(), key=OPENROUTER_KEY),
        "openrouter",
    )
    return service.verify_credential(
        receipt.bearer, receipt.view.csrf_token,
        CredentialCommand(
            operation_id=uuid4(), expected_revision=saved.revision),
        "openrouter",
    )


def test_deepseek_and_openrouter_coexist_and_revisions_are_independent(chat_env):
    service, alice, _, _ = chat_env
    deepseek = connect_key(service, alice)
    openrouter = connect_openrouter(service, alice)

    listed = service.credentials(alice.bearer).credentials
    assert [(item.provider, item.verified) for item in listed] == [
        ("deepseek", True), ("openrouter", True)]
    assert service.credential(alice.bearer, "deepseek") == deepseek
    assert service.credential(alice.bearer, "openrouter") == openrouter

    replacement = service.save_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialWrite(
            operation_id=uuid4(), key=OPENROUTER_KEY,
            expected_revision=openrouter.revision),
        "openrouter",
    )
    reverified = service.verify_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialCommand(
            operation_id=uuid4(), expected_revision=replacement.revision),
        "openrouter",
    )
    assert reverified.revision == openrouter.revision + 2
    assert reverified.generation == openrouter.generation + 1
    assert service.credential(alice.bearer, "deepseek") == deepseek

    with service.engine.begin() as conn:
        rows = conn.execute(sa.select(
            chat.connections.c.provider, chat.connections.c.id
        ).where(
            chat.connections.c.account_id == alice.view.account.id
        ).order_by(chat.connections.c.provider)).all()
    assert [row.provider for row in rows] == ["deepseek", "openrouter"]


def test_duplicate_provider_connection_is_forbidden(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    with service.engine.begin() as conn:
        source = conn.execute(sa.select(chat.connections).where(
            chat.connections.c.account_id == alice.view.account.id,
            chat.connections.c.provider == "deepseek",
        )).mappings().one()
        duplicate = dict(source)
        duplicate["id"] = uuid4()
        duplicate["last_operation_id"] = uuid4()
        with pytest.raises(sa.exc.IntegrityError):
            with conn.begin_nested():
                conn.execute(sa.insert(chat.connections).values(**duplicate))


def test_provider_aware_aes_keeps_deepseek_backward_compatible(chat_env):
    service, alice, _, _ = chat_env
    root = service.policy.root_key_bytes()
    account_id = alice.view.account.id

    deepseek_id = uuid4()
    nonce, ciphertext = encrypt(
        root, account_id, deepseek_id, 3, KEY)
    assert decrypt(
        root, account_id, deepseek_id, 3, nonce, ciphertext,
        "deepseek") == KEY

    openrouter_id = uuid4()
    nonce2, ciphertext2 = encrypt(
        root, account_id, openrouter_id, 4,
        OPENROUTER_KEY, "openrouter")
    assert decrypt(
        root, account_id, openrouter_id, 4, nonce2, ciphertext2,
        "openrouter") == OPENROUTER_KEY
    with pytest.raises(InvalidTag):
        decrypt(
            root, account_id, openrouter_id, 4,
            nonce2, ciphertext2, "deepseek")


def test_openrouter_save_verify_reserves_rate_headroom(chat_env):
    service, alice, _, _ = chat_env
    service.providers["openrouter"] = FakeOpenRouterProvider()
    with service.engine.begin() as conn:
        now = service.now()
        start = now - now % 300
        conn.execute(sa.insert(chat.limits).values(
            account_id=alice.view.account.id,
            kind="credential", window_start=start,
            count=CREDENTIAL_WINDOW_LIMIT - 1))

    with pytest.raises(ChatError, match="chat_rate_limited"):
        service.save_credential(
            alice.bearer, alice.view.csrf_token,
            CredentialWrite(
                operation_id=uuid4(), key=OPENROUTER_KEY),
            "openrouter",
        )
    current = service.credential(alice.bearer, "openrouter")
    assert not current.configured
    with service.engine.begin() as conn:
        count = conn.execute(sa.select(chat.limits.c.count).where(
            chat.limits.c.account_id == alice.view.account.id,
            chat.limits.c.kind == "credential",
        )).scalar_one()
    assert count == CREDENTIAL_WINDOW_LIMIT - 1


def test_model_resolves_exact_provider_connection_snapshot(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    connect_openrouter(service, alice)
    first = service.create_thread(
        alice.bearer, alice.view.csrf_token, "deepseek")
    second = service.create_thread(
        alice.bearer, alice.view.csrf_token, "openrouter")

    deepseek_request = request(
        service, alice, first.id, "deepseek",
        model="deepseek-flash")
    openrouter_request = request(
        service, alice, second.id, "openrouter",
        model="openrouter-auto")

    with service.engine.begin() as conn:
        connections = {
            row["provider"]: row for row in conn.execute(
                sa.select(chat.connections).where(
                    chat.connections.c.account_id
                    == alice.view.account.id)
            ).mappings()
        }
        rows = {
            row["id"]: row for row in conn.execute(
                sa.select(chat.requests).where(
                    chat.requests.c.id.in_(
                        [deepseek_request.id, openrouter_request.id]))
            ).mappings()
        }
    assert rows[deepseek_request.id]["connection_id"] == connections["deepseek"]["id"]
    assert rows[deepseek_request.id]["credential_generation"] == connections["deepseek"]["generation"]
    assert rows[openrouter_request.id]["connection_id"] == connections["openrouter"]["id"]
    assert rows[openrouter_request.id]["credential_generation"] == connections["openrouter"]["generation"]


def test_openrouter_model_without_openrouter_credential_is_rejected(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = service.create_thread(
        alice.bearer, alice.view.csrf_token, None)
    with pytest.raises(ChatError, match="credential_not_verified"):
        request(
            service, alice, thread.id, "No fallback",
            model="openrouter-auto")


def test_openrouter_streaming_adapter_and_fixed_origin():
    import json

    messages = [{"role": "user", "content": "hello"}]

    def open_response(outbound, timeout):
        assert outbound.full_url == "https://openrouter.ai/api/v1/chat/completions"
        body = json.loads(outbound.data)
        assert body == {
            "model": "openrouter/auto",
            "messages": messages,
            "stream": True,
            "max_tokens": 512,
        }
        assert outbound.get_header("Authorization") == "Bearer synthetic-openrouter-key"
        response = io.BytesIO(
            b'data: {"choices":[{"delta":{"content":"open"},"finish_reason":null}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"router"},"finish_reason":"stop"}]}\n\n'
            b'data: [DONE]\n\n')
        response.status = 200
        return response

    provider = OpenRouterProvider()
    provider.opener = SimpleNamespace(open=open_response)
    result = "".join(provider.stream(
        "synthetic-openrouter-key", "openrouter/auto",
        messages, 512, 15, Event()))
    assert result == "openrouter"


@pytest.mark.parametrize(("status", "code"), [
    (401, "credential_rejected"),
    (402, "provider_balance"),
    (429, "provider_rate_limited"),
    (503, "provider_overloaded"),
])
def test_openrouter_verify_error_mapping(status, code):
    def failing(_request, timeout):
        error = HTTPError(
            "https://openrouter.ai/api/v1/key",
            status, "provider failure", {}, io.BytesIO(b"{}"))
        raise error

    provider = OpenRouterProvider()
    provider.opener = SimpleNamespace(open=failing)
    with pytest.raises(ProviderFailure, match=code):
        provider.verify("synthetic-openrouter-key")


def test_multi_provider_migration_is_forward_and_data_preserving():
    path = ROOT / "apps/api/migrations/versions/0014_chat_multi_provider.py"
    text = path.read_text(encoding="utf-8")
    assert 'down_revision = "0013_chat_vision"' in text
    assert "chat_connection_account_provider" in text
    assert "provider IN ('deepseek','openrouter')" in text
    upper = text.upper()
    assert " UPDATE " not in upper
    assert " DELETE " not in upper
