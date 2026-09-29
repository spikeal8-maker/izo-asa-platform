"""Strict fal response/URL validation."""
import json
from urllib.parse import urlsplit

from .fal_core import APP_ID, FalPermanent, QUEUE_ORIGIN


def json_object(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FalPermanent("provider_invalid_json") from None
    if not isinstance(value, dict):
        raise FalPermanent("provider_invalid_json")
    return value


def request_id(value: object) -> str:
    if not isinstance(value, str) or not 8 <= len(value) <= 160:
        raise FalPermanent("provider_invalid_request_id")
    if any(not (c.isalnum() or c in "-_") for c in value):
        raise FalPermanent("provider_invalid_request_id")
    return value


def operation_url(value: object, request: str, kind: str) -> str:
    base = f"/{APP_ID}/requests/{request}"
    defaults = {"status": base + "/status", "cancel": base + "/cancel", "response": base}
    if value is None:
        return QUEUE_ORIGIN + defaults[kind]
    if not isinstance(value, str):
        raise FalPermanent("provider_invalid_operation_url")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise FalPermanent("provider_invalid_operation_url") from None
    if (parsed.scheme != "https" or parsed.hostname != "queue.fal.run" or port not in (None, 443)
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
        raise FalPermanent("provider_invalid_operation_url")
    allowed = {defaults[kind]}
    if kind == "response":
        allowed.add(base + "/response")
    if parsed.path not in allowed:
        raise FalPermanent("provider_invalid_operation_url")
    return value


def media_url(value: object) -> str:
    if not isinstance(value, str):
        raise FalPermanent("provider_invalid_media_url")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise FalPermanent("provider_invalid_media_url") from None
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or port not in (None, 443)
            or parsed.username is not None or parsed.password is not None or parsed.fragment
            or not (host == "fal.media" or host.endswith(".fal.media"))):
        raise FalPermanent("provider_invalid_media_url")
    return value
