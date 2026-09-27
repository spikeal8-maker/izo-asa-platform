"""OpenRouter BYOK, catalog and paid outcome tests."""
import json
import importlib.util
import io
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.exceptions import InvalidTag
from sqlalchemy.exc import IntegrityError

from izo.chat import tables as chat
from izo.chat.catalog import (
    CATALOG_TTL_SECONDS, CATALOG_FAILURE_TTL_SECONDS,
    OpenRouterCatalogCache, parse_openrouter_text_models,
)
from izo.chat.credential_crypto import operation_fingerprint
from izo.chat.credentials import ChatError, decrypt
from izo.chat.provider_openrouter import FakeOpenRouterProvider, OpenRouterProvider
from izo.chat.provider import ProviderFailure
from izo.chat.schemas import (
    CredentialCommand, CredentialWrite, OpenRouterCatalogModel,
)
from test_chat import chat_env, connect_key, new_thread, request
from test_chat_http import http_env, signup


def _model():
    return OpenRouterCatalogModel(
        id="vendor/text", name="Text model", provider="vendor",
        context_length=32768, input_per_million_usd=1,
        output_per_million_usd=2,
    )


def _install_openrouter(service):
    service.providers["openrouter"] = FakeOpenRouterProvider()
    service._openrouter_catalog = OpenRouterCatalogCache(
        clock=service.clock, fetcher=lambda: [_model()])


def _connect_openrouter(service, receipt):
    saved = service.save_credential(
        receipt.bearer, receipt.view.csrf_token,
        CredentialWrite(operation_id=uuid4(), key=FakeOpenRouterProvider.TEST_KEY),
        "openrouter")
    return service.verify_credential(
        receipt.bearer, receipt.view.csrf_token,
        CredentialCommand(operation_id=uuid4(), expected_revision=saved.revision),
        "openrouter")


def _ready(chat_env):
    service, alice, _, _ = chat_env
    _install_openrouter(service)
    _connect_openrouter(service, alice)
    return service, alice, new_thread(service, alice)


def test_deepseek_legacy_hash_and_provider_aad_remain_separate(chat_env):
    service, alice, bob, _ = chat_env
    _install_openrouter(service)
    connect_key(service, alice)
    verified = _connect_openrouter(service, alice)
    assert verified.verified and verified.provider == "openrouter"
    assert {item.provider for item in service.credentials(alice.bearer).credentials} == {
        "deepseek", "openrouter"}
    with service.engine.begin() as conn:
        rows = conn.execute(sa.select(chat.connections).where(
            chat.connections.c.account_id == alice.view.account.id)).mappings().all()
    deepseek = next(row for row in rows if row["provider"] == "deepseek")
    openrouter = next(row for row in rows if row["provider"] == "openrouter")
    root = service.policy.root_key_bytes()
    args = (root, alice.view.account.id, openrouter["id"],
            openrouter["generation"], openrouter["nonce"], openrouter["ciphertext"])
    assert decrypt(*args, "openrouter") == FakeOpenRouterProvider.TEST_KEY
    with pytest.raises(InvalidTag):
        decrypt(*args, "deepseek")
    with pytest.raises(InvalidTag):
        decrypt(root, bob.view.account.id, *args[2:], "openrouter")
    assert not service.credential(bob.bearer, "openrouter").configured
    assert deepseek["enabled"]
    assert operation_fingerprint(root, "save", b"legacy") == operation_fingerprint(
        root, "save:deepseek", b"legacy")


def test_dynamic_model_own_key_and_russian_preference(chat_env):
    service, alice, thread = _ready(chat_env)
    connect_key(service, alice)
    policy = service.public_policy(alice.bearer)
    auto = next(item for item in policy.models if item.id == "openrouter-auto")
    assert auto.provider == "openrouter"
    assert auto.price.input_kopeks_per_million is None
    accepted = request(service, alice, thread.id, "Ответь кратко",
                       model="vendor/text")
    with service.engine.begin() as conn:
        row = conn.execute(sa.select(chat.requests).where(
            chat.requests.c.id == accepted.id)).mappings().one()
    key, provider, model, messages = service._context_and_key(
        alice.view.account.id, row)
    assert key == FakeOpenRouterProvider.TEST_KEY
    assert (provider, model) == ("openrouter", "vendor/text")
    assert messages[0]["role"] == "system" and "русском" in messages[0]["content"]
    service._openrouter_catalog.get = lambda: (_ for _ in ()).throw(
        ProviderFailure("catalog_unavailable"))
    assert "message.done" in "".join(service.stream_events(alice.bearer, accepted.id))
    assert "Ответ OpenRouter test" in service.thread_detail(alice.bearer, thread.id).messages[-1].content


def test_unknown_catalog_model_and_unavailable_provider_fail_closed(chat_env):
    service, alice, thread = _ready(chat_env)
    with pytest.raises(ChatError, match="model_not_allowed"):
        request(service, alice, thread.id, "hello", model="browser/forged")
    service.providers.pop("openrouter")
    with pytest.raises(ChatError, match="provider_unavailable"):
        service.provider_for("openrouter")


def test_failed_provider_verification_replay_never_marks_key_verified(chat_env):
    service, alice, _, _ = chat_env
    _install_openrouter(service)
    saved = service.save_credential(
        alice.bearer, alice.view.csrf_token,
        CredentialWrite(operation_id=uuid4(), key="wrong-openrouter-key"),
        "openrouter")
    operation = CredentialCommand(
        operation_id=uuid4(), expected_revision=saved.revision)
    for _ in range(2):
        with pytest.raises(ChatError, match="credential_rejected"):
            service.verify_credential(
                alice.bearer, alice.view.csrf_token, operation, "openrouter")
    assert not service.credential(alice.bearer, "openrouter").verified


def test_catalog_outage_blocks_new_request_but_not_idempotent_replay(chat_env):
    service, alice, bob, clock = chat_env
    _install_openrouter(service)
    _connect_openrouter(service, alice)
    thread = new_thread(service, alice)
    request_id = uuid4()
    first = request(service, alice, thread.id, "safe replay",
                    model="vendor/text", request_id=request_id)
    service._openrouter_catalog.fetcher = lambda: (_ for _ in ()).throw(
        ProviderFailure("catalog_unavailable"))
    clock[0] += CATALOG_TTL_SECONDS + 1
    replay = request(service, alice, thread.id, "safe replay",
                     model="vendor/text", request_id=request_id)
    assert replay.id == first.id
    with pytest.raises(ChatError, match="catalog_unavailable"):
        request(service, alice, thread.id, "new",
                model="vendor/text")
    bob_thread = new_thread(service, bob)
    for request_id in (first.id, uuid4()):
        with pytest.raises(ChatError, match="catalog_unavailable"):
            request(service, bob, bob_thread.id, "same",
                    model="vendor/text", request_id=request_id)


def test_db_rejects_duplicate_provider_and_unknown_provider(chat_env):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    with service.engine.begin() as conn:
        original = dict(conn.execute(sa.select(chat.connections).where(
            chat.connections.c.account_id == alice.view.account.id)).mappings().one())
    duplicate = {**original, "id": uuid4(), "last_operation_id": uuid4()}
    invalid = {**duplicate, "provider": "browser-selected"}
    for candidate in (duplicate, invalid):
        with pytest.raises(IntegrityError):
            with service.engine.begin() as conn:
                conn.execute(sa.insert(chat.connections).values(**candidate))


def test_catalog_filters_non_text_and_non_finite_prices():
    def row(model, outputs=("text",), price="0.000001"):
        item = {"id": model, "architecture": {
            "input_modalities": ["text"], "output_modalities": list(outputs)}}
        if price is not None:
            item["pricing"] = {"prompt": price, "completion": "0.000002"}
        return item
    parsed = parse_openrouter_text_models({"data": [
        row("vendor/text"), row("vendor/image", ("image",)),
        row("vendor/nan", price="NaN"),
        {**row("vendor/infinite-context"), "context_length": 1e999},
        {**row("vendor/infinite-created"), "created": 1e999},
        row("vendor/unknown", price=None),
    ]})
    assert {item.id for item in parsed} == {"vendor/text", "vendor/unknown"}
    unknown = next(item for item in parsed if item.id == "vendor/unknown")
    assert unknown.input_per_million_usd is None
    assert unknown.output_per_million_usd is None


def test_catalog_failure_backoff_then_recovers():
    clock, calls = [0], []
    def fail():
        calls.append(1)
        raise ProviderFailure("catalog_unavailable")
    cache = OpenRouterCatalogCache(clock=lambda: clock[0], fetcher=fail)
    for _ in range(2):
        with pytest.raises(ProviderFailure, match="catalog_unavailable"):
            cache.get()
    assert len(calls) == 1
    cache.fetcher = lambda: [_model()]
    clock[0] = CATALOG_FAILURE_TTL_SECONDS
    assert not cache.get().stale and len(calls) == 1


@pytest.mark.parametrize("failure,unknown", [
    ("provider_unavailable", True), ("provider_stream_interrupted", True),
    ("request_expired", True), ("restart", True),
    ("provider_rejected", False),
])
def test_paid_outcome_barrier_and_known_rejection(chat_env, failure, unknown):
    service, alice, thread = _ready(chat_env)
    first = request(service, alice, thread.id, "charged?", model="vendor/text")
    if failure == "restart":
        with service.engine.begin() as conn:
            conn.execute(sa.update(chat.requests).where(chat.requests.c.id == first.id)
                         .values(state="streaming"))
        service = type(service)(service.auth, service.policy, service.provider,
                                clock=service.clock, providers=service.providers,
                                openrouter_catalog=service._openrouter_catalog)
    else:
        service.providers["openrouter"].stream = lambda *args: (
            _ for _ in ()).throw(ProviderFailure(failure))
        events = "".join(service.stream_events(alice.bearer, first.id))
    expected = "provider_outcome_unknown" if unknown else failure
    if failure != "restart":
        assert expected in events
    assert service.request(alice.bearer, first.id).error_code == expected
    if unknown:
        with pytest.raises(ChatError, match="provider_outcome_unknown"):
            request(service, alice, thread.id, "again", model="vendor/text")
    else:
        request(service, alice, thread.id, "again", model="vendor/text")
    assert request(service, alice, thread.id, "charged?", model="vendor/text",
                   request_id=first.id).id == first.id


def test_http_provider_routes_reject_unknown_and_hide_key(http_env):
    _, service, client = http_env
    _install_openrouter(service)
    signup(None, client, "alice@example.invalid")
    listed = client.get("/api/v1/chat/credentials")
    assert listed.status_code == 200
    assert [item["provider"] for item in listed.json()["credentials"]] == [
        "deepseek", "openrouter"]
    catalog = client.get("/api/v1/chat/catalog/openrouter")
    assert catalog.status_code == 200
    assert catalog.json()["models"][0]["id"] == "vendor/text"
    unknown = client.get("/api/v1/chat/credentials/browser-chosen")
    assert unknown.status_code == 422
    secret = "synthetic-key-must-not-echo\ninvalid"
    rejected = client.post("/api/v1/chat/credentials/openrouter", json={
        "operation_id": str(uuid4()), "key": secret})
    assert rejected.status_code == 422
    assert secret not in rejected.text and "synthetic-key" not in rejected.text


def test_openrouter_wire_has_fixed_origin_and_no_deepseek_thinking_flag():
    request_body = OpenRouterProvider._chat_request(
        "synthetic-test-key", "vendor/text",
        [{"role": "system", "content": "Отвечай на русском языке"},
         {"role": "user", "content": "Привет"}], 512)
    assert request_body.full_url == "https://openrouter.ai/api/v1/chat/completions"
    body = json.loads(request_body.data)
    assert body["model"] == "vendor/text" and "thinking" not in body


def test_forward_migration_has_admin_parent_and_provider_constraints():
    path = (Path(__file__).resolve().parents[1]
            / "apps/api/migrations/versions/0014_chat_multi_provider.py")
    spec = importlib.util.spec_from_file_location("chat_multi_provider_0014", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "0013_admin_catalog"
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        migration.upgrade()
    ddl = output.getvalue()
    assert "chat_connection_account_provider" in ddl
    assert "provider IN ('deepseek','openrouter')" in ddl
