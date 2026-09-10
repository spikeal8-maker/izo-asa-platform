"""Bounded OpenRouter Images API client. Never logs prompt, key or response body."""
import base64
import binascii
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://openrouter.ai/api/v1/images"
MAX_JSON = 96 * 1024 * 1024
MAX_IMAGE = 65 * 1024 * 1024


class ProviderError(Exception):
    def __init__(self, code: str, *, request_may_have_completed: bool):
        super().__init__(code)
        self.code = code
        self.request_may_have_completed = request_may_have_completed


@dataclass(frozen=True)
class ProviderImage:
    data: bytes
    media_type: str
    cost_usd: Decimal | None
    provider_ref: str | None


def _cost(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ProviderError("provider_invalid_response", request_may_have_completed=True) from None
    if result < 0 or not result.is_finite():
        raise ProviderError("provider_invalid_response", request_may_have_completed=True)
    return result


def generate(snapshot: dict, prompt: str, api_key: str, *, timeout: int,
             opener=urlopen) -> ProviderImage:
    body = json.dumps({
        "model": snapshot["model"],
        "prompt": prompt,
        "resolution": snapshot["resolution"],
        "output_format": snapshot["output_format"],
        "n": 1,
        "provider": {"allow_fallbacks": snapshot["allow_fallbacks"]},
    }, separators=(",", ":")).encode()
    request = Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "IZO-ASA/1",
    })
    try:
        response = opener(request, timeout=timeout)
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > MAX_JSON:
            raise ProviderError("provider_response_too_large", request_may_have_completed=True)
        raw = response.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise ProviderError("provider_response_too_large", request_may_have_completed=True)
    except ProviderError:
        raise
    except HTTPError as exc:
        raise ProviderError("provider_rejected", request_may_have_completed=True) from exc
    except (URLError, TimeoutError, OSError, ValueError):
        raise ProviderError("provider_outcome_unknown", request_may_have_completed=True) from None
    try:
        payload = json.loads(raw)
        items = payload.get("data")
        item = items[0] if isinstance(items, list) and len(items) == 1 else None
        encoded = item.get("b64_json") if isinstance(item, dict) else None
        media = item.get("media_type") if isinstance(item, dict) else None
        if not isinstance(encoded, str) or not encoded or len(encoded) > (MAX_IMAGE * 4 // 3 + 16):
            raise ValueError
        if media not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError
        data = base64.b64decode(encoded, validate=True)
        if not 0 < len(data) <= MAX_IMAGE:
            raise ValueError
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        ref = payload.get("id") if isinstance(payload.get("id"), str) else None
        if ref is not None and len(ref) > 200:
            ref = None
        return ProviderImage(data, media, _cost(usage.get("cost")), ref)
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError):
        raise ProviderError("provider_invalid_response", request_may_have_completed=True) from None
