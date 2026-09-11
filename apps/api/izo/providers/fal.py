"""Bounded fal.ai queue adapter for one approved FLUX.2 [klein] capability."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import socket
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ID = "fal-ai/flux-2/klein/4b"
PROVIDER = "fal"
CONNECTION_ID = "fal-klein-4b-v1"
CREDENTIAL_REF = "env:IZO_FAL_KEY:v1"
QUEUE_ORIGIN = "https://queue.fal.run"
MAX_JSON = 1_000_000


class FalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_FAL_", extra="ignore", hide_input_in_errors=True)
    enabled: bool = False
    key: SecretStr = SecretStr("")
    credential_version: str = Field(default="v1", pattern=r"^[a-zA-Z0-9._-]{1,40}$")
    price_microusd_per_mp: int = Field(default=0, ge=0, le=1_000_000_000)
    max_cost_microusd: int = Field(default=0, ge=0, le=1_000_000_000)
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)
    media_timeout_seconds: int = Field(default=60, ge=5, le=180)
    poll_seconds: int = Field(default=2, ge=1, le=30)
    queue_start_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    media_retention_seconds: int = Field(default=3600, ge=300, le=604800)

    def estimated_cost_microusd(self, width: int, height: int) -> int | None:
        if self.price_microusd_per_mp <= 0:
            return None
        return max(1, math.ceil(width * height * self.price_microusd_per_mp / 1_000_000))

    def admission_available(self, width: int, height: int) -> bool:
        estimate = self.estimated_cost_microusd(width, height)
        return bool(self.enabled and estimate is not None and self.max_cost_microusd >= estimate)

    def require_credential(self) -> str:
        value = self.key.get_secret_value()
        if not value:
            raise FalAuthRequired("provider_auth_required")
        return value

    def require_worker_ready(self) -> str:
        estimate_ready = self.price_microusd_per_mp > 0 and self.max_cost_microusd > 0
        value = self.key.get_secret_value()
        if not self.enabled or not estimate_ready or not value:
            raise RuntimeError("fal provider requires explicit enable, budget, price and credential")
        return value


class FalError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class FalSubmissionUnknown(FalError):
    """The submit request may have been accepted. Never repeat it automatically."""


class FalRejected(FalError):
    """A definite pre-acceptance HTTP rejection; safe to release product reservation."""


class FalTransient(FalError):
    """Request ID is known, so status/result can be retried without regenerating."""


class FalAuthRequired(FalError):
    """Existing provider request needs operator credential intervention, not failover."""


class FalPermanent(FalError):
    """Provider returned a permanent invalid response for a known request."""


class FalRequestMissing(FalPermanent):
    """A known request is no longer pollable; only a confirmed cancel may make this terminal."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrlLibTransport:
    """Small transport so tests can replace network without monkeypatching domain code."""
    def __init__(self):
        self.opener = build_opener(_NoRedirect)

    def request(self, method: str, url: str, *, headers: Mapping[str, str] | None = None,
                body: bytes | None = None, timeout: int = 30, maximum: int = MAX_JSON) -> HttpResponse:
        request = Request(url, data=body, headers=dict(headers or {}), method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                data = response.read(maximum + 1)
                if len(data) > maximum:
                    raise FalPermanent("provider_response_too_large")
                return HttpResponse(response.status, dict(response.headers.items()), data)
        except HTTPError as exc:
            data = exc.read(maximum + 1)
            if len(data) > maximum:
                data = b""
            return HttpResponse(exc.code, dict(exc.headers.items()) if exc.headers else {}, data)
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise ConnectionError("provider transport unavailable") from exc


@dataclass(frozen=True)
class FalHandle:
    request_id: str
    status_url: str
    response_url: str
    cancel_url: str


@dataclass(frozen=True)
class FalStatus:
    state: str
    has_error: bool = False


@dataclass(frozen=True)
class FalImage:
    data: bytes
    content_type: str


def _json(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FalPermanent("provider_invalid_json") from None
    if not isinstance(value, dict):
        raise FalPermanent("provider_invalid_json")
    return value


def _request_id(value: object) -> str:
    if not isinstance(value, str) or not 8 <= len(value) <= 160:
        raise FalPermanent("provider_invalid_request_id")
    if any(not (c.isalnum() or c in "-_") for c in value):
        raise FalPermanent("provider_invalid_request_id")
    return value


def _operation_url(value: object, request_id: str, kind: str) -> str:
    base = f"/{APP_ID}/requests/{request_id}"
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


def _media_url(value: object) -> str:
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


class FalAdapter:
    def __init__(self, settings: FalSettings | None = None, transport=None):
        self.settings = settings or FalSettings()
        self.transport = transport or UrlLibTransport()

    @property
    def connection_id(self) -> str:
        return CONNECTION_ID

    @property
    def credential_ref(self) -> str:
        return f"env:IZO_FAL_KEY:{self.settings.credential_version}"

    def estimate(self, width: int, height: int) -> int:
        value = self.settings.estimated_cost_microusd(width, height)
        if value is None or value > self.settings.max_cost_microusd:
            raise FalRejected("provider_budget_exceeded")
        return value

    def _headers(self, *, submit=False) -> dict[str, str]:
        key = (self.settings.require_worker_ready() if submit
               else self.settings.require_credential())
        headers = {"Authorization": f"Key {key}", "Accept": "application/json"}
        if submit:
            headers.update({
                "Content-Type": "application/json",
                "X-Fal-Store-IO": "0",
                "X-Fal-Request-Timeout": str(self.settings.queue_start_timeout_seconds),
                "X-Fal-Object-Lifecycle-Preference": json.dumps(
                    {"expiration_duration_seconds": self.settings.media_retention_seconds},
                    separators=(",", ":")),
            })
        return headers

    def submit(self, draft) -> FalHandle:
        payload = json.dumps({
            "prompt": draft.prompt,
            "image_size": {"width": draft.width, "height": draft.height},
            "num_images": 1,
            "enable_safety_checker": True,
            "output_format": "png",
        }, separators=(",", ":")).encode()
        try:
            response = self.transport.request("POST", f"{QUEUE_ORIGIN}/{APP_ID}",
                headers=self._headers(submit=True), body=payload,
                timeout=self.settings.request_timeout_seconds, maximum=MAX_JSON)
        except ConnectionError:
            raise FalSubmissionUnknown("provider_submission_unknown") from None
        if 400 <= response.status < 500:
            raise FalRejected("provider_rejected")
        if response.status >= 500 or response.status < 200 or response.status >= 300:
            raise FalSubmissionUnknown("provider_submission_unknown")
        try:
            value = _json(response.body)
            request_id = _request_id(value.get("request_id"))
            return FalHandle(request_id=request_id,
                status_url=_operation_url(value.get("status_url"), request_id, "status"),
                response_url=_operation_url(value.get("response_url"), request_id, "response"),
                cancel_url=_operation_url(value.get("cancel_url"), request_id, "cancel"))
        except FalPermanent:
            # A 2xx submit without a usable handle may already have incurred provider work.
            raise FalSubmissionUnknown("provider_submission_unknown") from None

    def _known(self, method: str, url: str, *, maximum: int = MAX_JSON) -> HttpResponse:
        try:
            response = self.transport.request(method, url, headers=self._headers(),
                timeout=self.settings.request_timeout_seconds, maximum=maximum)
        except ConnectionError:
            raise FalTransient("provider_temporarily_unavailable") from None
        if response.status in (401, 403):
            raise FalAuthRequired("provider_auth_required")
        if response.status == 429 or response.status >= 500:
            raise FalTransient("provider_temporarily_unavailable")
        return response

    def status(self, handle: FalHandle) -> FalStatus:
        response = self._known("GET", handle.status_url)
        if response.status == 404:
            raise FalRequestMissing("provider_request_missing")
        if response.status != 200:
            raise FalPermanent("provider_status_rejected")
        value = _json(response.body)
        state = value.get("status")
        if state not in {"IN_QUEUE", "IN_PROGRESS", "COMPLETED"}:
            raise FalPermanent("provider_invalid_status")
        return FalStatus(state=state, has_error=bool(value.get("error") or value.get("error_type")))

    def result(self, handle: FalHandle, *, width: int, height: int, maximum: int) -> FalImage:
        response = self._known("GET", handle.response_url)
        if response.status == 404:
            raise FalPermanent("provider_request_missing")
        if response.status != 200:
            raise FalPermanent("provider_result_rejected")
        value = _json(response.body)
        images = value.get("images")
        if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
            raise FalPermanent("provider_invalid_result")
        image = images[0]
        if image.get("width") not in (None, width) or image.get("height") not in (None, height):
            raise FalPermanent("provider_invalid_result")
        content_type = image.get("content_type") or "image/png"
        if content_type != "image/png":
            raise FalPermanent("provider_invalid_result")
        url = _media_url(image.get("url"))
        try:
            media = self.transport.request("GET", url, headers={"Accept": "image/png"},
                timeout=self.settings.media_timeout_seconds, maximum=maximum)
        except ConnectionError:
            raise FalTransient("provider_output_unavailable") from None
        if media.status != 200:
            if media.status == 429 or media.status >= 500:
                raise FalTransient("provider_output_unavailable")
            raise FalPermanent("provider_invalid_result")
        header = next((v for k, v in media.headers.items() if k.lower() == "content-type"), "")
        if header.split(";", 1)[0].strip().lower() != "image/png":
            raise FalPermanent("provider_invalid_result")
        return FalImage(media.body, "image/png")

    def cancel(self, handle: FalHandle) -> str:
        response = self._known("PUT", handle.cancel_url)
        if response.status == 202:
            return "requested"
        value = _json(response.body) if response.body else {}
        if response.status == 400 and value.get("status") == "ALREADY_COMPLETED":
            return "completed"
        if response.status == 404 and value.get("status") == "NOT_FOUND":
            return "missing"
        raise FalPermanent("provider_cancel_rejected")
