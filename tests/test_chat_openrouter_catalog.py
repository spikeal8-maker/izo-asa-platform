"""Donor-adapted OpenRouter text catalog, cache, validation and dev TLS bridge."""
from pathlib import Path
from uuid import uuid4

import pytest

from izo.chat.catalog import (
    CATALOG_TTL_SECONDS, OpenRouterCatalogCache,
    parse_openrouter_text_models,
)
from izo.chat.errors import ChatError
from izo.chat.provider import ProviderFailure
from izo.chat.schemas import OpenRouterCatalogModel
from test_chat import chat_env, request
from test_chat_multi_provider import connect_openrouter

ROOT = Path(__file__).resolve().parents[1]


def row(
    model_id="vendor/model", name="Model", *,
    inputs=("text",), outputs=("text",),
    prompt="0.000001", completion="0.000002",
    context=32768, created=123,
):
    return {
        "id": model_id, "name": name, "created": created,
        "architecture": {
            "input_modalities": list(inputs),
            "output_modalities": list(outputs),
        },
        "pricing": {"prompt": prompt, "completion": completion},
        "context_length": context,
    }


def model(model_id="vendor/model", name="Model"):
    return OpenRouterCatalogModel(
        id=model_id, name=name, provider=model_id.split("/", 1)[0],
        context_length=32768,
        input_per_million_usd=1,
        output_per_million_usd=2,
        created=123,
    )


def test_donor_text_catalog_parser_filters_and_normalizes():
    payload = {"data": [
        row("vendor/good", "Good"),
        row("vendor/no-text-output", outputs=("image",)),
        row("vendor/no-text-input", inputs=("image",)),
        row("vendor/negative", prompt="-1"),
        row("x" * 65),
        "not-a-model",
    ]}
    parsed = parse_openrouter_text_models(payload)
    assert [item.id for item in parsed] == ["vendor/good"]
    item = parsed[0]
    assert item.provider == "vendor"
    assert item.context_length == 32768
    assert item.input_per_million_usd == 1
    assert item.output_per_million_usd == 2
    assert item.created == 123


def test_catalog_cache_ttl_and_stale_last_known_good():
    now = [1000]
    calls = [0]

    def fetcher():
        calls[0] += 1
        if calls[0] == 1:
            return [model()]
        raise ProviderFailure("catalog_unavailable")

    cache = OpenRouterCatalogCache(
        clock=lambda: now[0], fetcher=fetcher)
    fresh = cache.get()
    assert not fresh.stale and fresh.fetched_at == 1000
    assert calls[0] == 1

    now[0] += CATALOG_TTL_SECONDS - 1
    assert not cache.get().stale
    assert calls[0] == 1

    now[0] += 2
    stale = cache.get()
    assert stale.stale and stale.fetched_at == 1000
    assert [item.id for item in stale.models] == ["vendor/model"]
    assert calls[0] == 2


def test_catalog_without_last_known_good_fails_closed():
    cache = OpenRouterCatalogCache(
        clock=lambda: 1,
        fetcher=lambda: (_ for _ in ()).throw(
            ProviderFailure("catalog_unavailable")))
    with pytest.raises(ProviderFailure, match="catalog_unavailable"):
        cache.get()


def test_dynamic_model_validation_and_auto_mapping(chat_env):
    service, alice, _, _ = chat_env
    service._openrouter_catalog = OpenRouterCatalogCache(
        clock=service.clock,
        fetcher=lambda: [model("vendor/explicit", "Explicit")],
    )
    connect_openrouter(service, alice)

    assert service.resolve_model("openrouter-auto") == (
        "openrouter", "openrouter/auto")
    assert service.resolve_model("vendor/explicit") == (
        "openrouter", "vendor/explicit")
    with pytest.raises(ChatError, match="model_not_allowed"):
        service.resolve_model("browser/arbitrary")

    thread = service.create_thread(
        alice.bearer, alice.view.csrf_token, "catalog")
    accepted = request(
        service, alice, thread.id, "explicit",
        model="vendor/explicit")
    assert accepted.model == "vendor/explicit"


def test_dev_ca_bridge_keeps_tls_verification_and_production_unchanged():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    start = (ROOT / "dev-start.cmd").read_text(encoding="utf-8")
    dev = (ROOT / "compose.dev.yaml").read_text(encoding="utf-8")
    prod = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    script = (ROOT / "tools/dev-export-local-ca.ps1").read_text(
        encoding="utf-8")
    wrapper = (ROOT / "tools/dev-api-entrypoint.sh").read_text(
        encoding="utf-8")

    assert ".runtime/" in ignore
    assert "dev-export-local-ca.ps1" in start
    assert ".runtime/dev-ca:/run/izo-dev-ca:ro" in dev
    assert "dev-api-entrypoint.sh" in dev
    assert "SSL_CERT_FILE" in wrapper
    assert "ca-certificates.crt" in wrapper
    assert ".runtime/dev-ca" not in prod
    forbidden = (
        "verify=False", "CERT_NONE", "_create_unverified_context",
        "DangerousAcceptAnyServerCertificateValidator",
    )
    assert all(value not in script + wrapper + dev for value in forbidden)
