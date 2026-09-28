"""OpenRouter text catalog adapted from the read-only IZO_ASA donor."""
from __future__ import annotations

import json
import math
import socket
import time
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from ..catalog.schemas import Price
from .credential_read import ChatError
from .provider import ProviderFailure, _NoRedirect
from .provider_openrouter import OPENROUTER_BASE_URL
from .schemas import (
    ChatPolicyView, ModelView, OPENROUTER_AUTO_MODEL,
    OpenRouterCatalogModel, OpenRouterCatalogView,
    MAX_CHAT_ATTACHMENTS, MAX_CHAT_IMAGE_BYTES,
    MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS, MODEL_REVISION,
)

CATALOG_TTL_SECONDS = 600
CATALOG_FAILURE_TTL_SECONDS = 30
MAX_CATALOG_BYTES = 8 * 1024 * 1024
MAX_CATALOG_MODELS = 1000
MAX_MODEL_ID_CHARS = 64
# Adapter capability, independent of Admin's text pricing/modality catalog.
# https://api-docs.deepseek.com/guides/vision/
DEEPSEEK_VISION_MODELS = frozenset({"deepseek-flash"})


def parse_openrouter_text_models(payload) -> list[OpenRouterCatalogModel]:
    """Donor-compatible text/text filtering with target storage bounds."""
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    models: list[OpenRouterCatalogModel] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        architecture = row.get("architecture")
        architecture = architecture if isinstance(architecture, dict) else {}
        inputs = architecture.get("input_modalities")
        outputs = architecture.get("output_modalities")
        inputs = inputs if isinstance(inputs, list) else []
        outputs = outputs if isinstance(outputs, list) else []
        if "text" not in inputs or "text" not in outputs:
            continue
        model_id = str(row.get("id") or "").strip()
        if not model_id or len(model_id) > MAX_MODEL_ID_CHARS:
            continue
        pricing = row.get("pricing")
        pricing = pricing if isinstance(pricing, dict) else {}
        try:
            prompt = pricing.get("prompt")
            completion = pricing.get("completion")
            input_price = (float(prompt) * 1_000_000
                           if prompt is not None and prompt != "" else None)
            output_price = (float(completion) * 1_000_000
                            if completion is not None and completion != "" else None)
            context_length = int(row.get("context_length") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if (context_length < 0 or any(
                price is not None and (not math.isfinite(price) or price < 0)
                for price in (input_price, output_price))):
            continue
        try:
            created = int(row.get("created") or 0)
        except OverflowError:
            continue
        except (TypeError, ValueError):
            created = 0
        models.append(OpenRouterCatalogModel(
            id=model_id,
            name=str(row.get("name") or model_id)[:160],
            provider=model_id.split("/", 1)[0],
            context_length=min(context_length, 10_000_000),
            vision="image" in inputs,
            input_per_million_usd=(round(input_price, 6)
                                   if input_price is not None else None),
            output_per_million_usd=(round(output_price, 6)
                                    if output_price is not None else None),
            created=created if created > 0 else None,
        ))
        if len(models) >= MAX_CATALOG_MODELS:
            break
    models.sort(key=lambda item: (item.name.lower(), item.id))
    return models


def fetch_openrouter_text_models(timeout: int = 15) -> list[OpenRouterCatalogModel]:
    """Fixed-origin OpenRouter catalog fetch. TLS verification stays enabled."""
    opener = build_opener(_NoRedirect)
    request = Request(
        OPENROUTER_BASE_URL + "/models?output_modalities=text",
        headers={
            "Accept": "application/json",
            "User-Agent": "IZO-ASA/1",
            "X-Title": "IZO ASA",
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            data = response.read(MAX_CATALOG_BYTES + 1)
            if response.status != 200 or len(data) > MAX_CATALOG_BYTES:
                raise ProviderFailure("catalog_unavailable")
    except HTTPError:
        raise ProviderFailure("catalog_unavailable") from None
    except (URLError, TimeoutError, socket.timeout, OSError):
        raise ProviderFailure("catalog_unavailable") from None
    try:
        payload = json.loads(data)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise ProviderFailure("catalog_unavailable") from None
    models = parse_openrouter_text_models(payload)
    if not models:
        raise ProviderFailure("catalog_unavailable")
    return models


class OpenRouterCatalogCache:
    def __init__(self, clock=time.time, fetcher=fetch_openrouter_text_models):
        self.clock = clock
        self.fetcher = fetcher
        self._lock = Lock()
        self._models: list[OpenRouterCatalogModel] = []
        self._fetched_at: int | None = None
        self._failed_at: int | None = None

    def get(self) -> OpenRouterCatalogView:
        now = int(self.clock())
        with self._lock:
            if (self._models and self._fetched_at is not None
                    and now - self._fetched_at < CATALOG_TTL_SECONDS):
                return OpenRouterCatalogView(
                    models=list(self._models), stale=False,
                    fetched_at=self._fetched_at)
            if (self._failed_at is not None
                    and now - self._failed_at < CATALOG_FAILURE_TTL_SECONDS):
                if self._models:
                    return OpenRouterCatalogView(
                        models=list(self._models), stale=True,
                        fetched_at=self._fetched_at)
                raise ProviderFailure("catalog_unavailable")
            try:
                models = self.fetcher()
            except ProviderFailure:
                self._failed_at = int(self.clock())
                if self._models:
                    return OpenRouterCatalogView(
                        models=list(self._models), stale=True,
                        fetched_at=self._fetched_at)
                raise
            self._models = list(models)
            self._fetched_at = int(self.clock())
            self._failed_at = None
            return OpenRouterCatalogView(
                models=list(self._models), stale=False,
                fetched_at=self._fetched_at)


class CatalogMixin:
    @staticmethod
    def static_vision_supported(model_id: str, provider: str) -> bool:
        return provider == "deepseek" and model_id in DEEPSEEK_VISION_MODELS

    def public_policy(self, raw) -> ChatPolicyView:
        with self.engine.begin() as conn:
            self._account(conn, raw)
            head, models = self.catalog.public_text(conn)
        return ChatPolicyView(
            revision=f"{MODEL_REVISION}:catalog-{head['revision']}",
            default_model=head["default_model"],
            models=[ModelView(
                id=model.id, label=model.label, provider=model.provider,
                price=model.price, text=True,
                vision=self.static_vision_supported(model.id, model.provider),
                description=("Текст · Изображения" if self.static_vision_supported(
                    model.id, model.provider)
                             else "Текст")) for model in models] +
            ([ModelView(
                id=OPENROUTER_AUTO_MODEL, label="Автовыбор OpenRouter",
                provider="openrouter", price=Price(), text=True, vision=False,
                description="OpenRouter автоматически выбирает текстовую модель.")]
             if "openrouter" in self.providers else []),
            max_input_chars=MAX_INPUT_CHARS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            max_attachments=MAX_CHAT_ATTACHMENTS,
            max_image_bytes=MAX_CHAT_IMAGE_BYTES,
        )

    def openrouter_catalog(self, raw) -> OpenRouterCatalogView:
        with self.engine.begin() as conn:
            self._account(conn, raw)
        try:
            return self._openrouter_catalog.get()
        except ProviderFailure:
            raise ChatError(503, "catalog_unavailable") from None

    def resolve_model(self, model: str) -> tuple[str, str]:
        provider, provider_model, _ = self.model_admission(model)
        return provider, provider_model

    def model_admission(self, model: str) -> tuple[str, str, bool]:
        if model == OPENROUTER_AUTO_MODEL:
            return "openrouter", "openrouter/auto", False
        if "/" not in model:
            return "deepseek", model, self.static_vision_supported(model, "deepseek")
        try:
            catalog = self._openrouter_catalog.get()
        except ProviderFailure:
            raise ChatError(503, "catalog_unavailable") from None
        if catalog.stale:
            raise ChatError(503, "catalog_unavailable")
        selected = next((item for item in catalog.models if item.id == model), None)
        if selected is not None:
            return "openrouter", model, selected.vision
        raise ChatError(422, "model_not_allowed")
