"""OpenRouter text catalog adapted from the read-only IZO_ASA donor."""
from __future__ import annotations

import json
import socket
import time
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .errors import ChatError
from .provider import ProviderFailure, _NoRedirect
from .provider_openrouter import OPENROUTER_BASE_URL
from .schemas import OpenRouterCatalogModel, OpenRouterCatalogView

CATALOG_TTL_SECONDS = 600
MAX_CATALOG_BYTES = 8 * 1024 * 1024
MAX_CATALOG_MODELS = 1000
MAX_MODEL_ID_CHARS = 64


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
            input_price = float(pricing.get("prompt") or 0) * 1_000_000
            output_price = float(pricing.get("completion") or 0) * 1_000_000
            context_length = int(row.get("context_length") or 0)
        except (TypeError, ValueError):
            continue
        if input_price < 0 or output_price < 0 or context_length < 0:
            continue
        try:
            created = int(row.get("created") or 0)
        except (TypeError, ValueError):
            created = 0
        models.append(OpenRouterCatalogModel(
            id=model_id,
            name=str(row.get("name") or model_id)[:160],
            provider=model_id.split("/", 1)[0],
            context_length=min(context_length, 10_000_000),
            input_per_million_usd=round(input_price, 6),
            output_per_million_usd=round(output_price, 6),
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

    def get(self) -> OpenRouterCatalogView:
        now = int(self.clock())
        with self._lock:
            if (self._models and self._fetched_at is not None
                    and now - self._fetched_at < CATALOG_TTL_SECONDS):
                return OpenRouterCatalogView(
                    models=list(self._models), stale=False,
                    fetched_at=self._fetched_at)
            try:
                models = self.fetcher()
            except ProviderFailure:
                if self._models:
                    return OpenRouterCatalogView(
                        models=list(self._models), stale=True,
                        fetched_at=self._fetched_at)
                raise
            self._models = list(models)
            self._fetched_at = now
            return OpenRouterCatalogView(
                models=list(self._models), stale=False,
                fetched_at=self._fetched_at)


class CatalogMixin:
    def openrouter_catalog(self, raw) -> OpenRouterCatalogView:
        with self.engine.begin() as conn:
            self._account(conn, raw)
        try:
            return self._openrouter_catalog.get()
        except ProviderFailure:
            raise ChatError(503, "catalog_unavailable") from None

    def resolve_model(self, model: str) -> tuple[str, str]:
        spec = self.policy.model_spec(model)
        if spec:
            return spec[2], spec[3]
        try:
            catalog = self._openrouter_catalog.get()
        except ProviderFailure:
            raise ChatError(503, "catalog_unavailable") from None
        if any(item.id == model for item in catalog.models):
            return "openrouter", model
        raise ChatError(422, "model_not_allowed")
