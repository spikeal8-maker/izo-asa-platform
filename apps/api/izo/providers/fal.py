"""Bounded fal.ai adapter composed from transport, validation and value modules."""
import json

from .fal_core import (APP_ID, CONNECTION_ID, CREDENTIAL_REF, MAX_JSON, PROVIDER, QUEUE_ORIGIN,
                       FalAuthRequired, FalError, FalHandle, FalImage, FalPermanent, FalRejected,
                       FalRequestMissing, FalSettings, FalStatus, FalSubmissionUnknown, FalTransient,
                       HttpResponse)
from .fal_transport import UrlLibTransport
from .fal_validation import json_object, media_url, operation_url, request_id


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
        key = self.settings.require_worker_ready() if submit else self.settings.require_credential()
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
            value = json_object(response.body)
            rid = request_id(value.get("request_id"))
            return FalHandle(request_id=rid,
                status_url=operation_url(value.get("status_url"), rid, "status"),
                response_url=operation_url(value.get("response_url"), rid, "response"),
                cancel_url=operation_url(value.get("cancel_url"), rid, "cancel"))
        except FalPermanent:
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
        value = json_object(response.body)
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
        value = json_object(response.body)
        images = value.get("images")
        if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
            raise FalPermanent("provider_invalid_result")
        image = images[0]
        if image.get("width") not in (None, width) or image.get("height") not in (None, height):
            raise FalPermanent("provider_invalid_result")
        content_type = image.get("content_type") or "image/png"
        if content_type != "image/png":
            raise FalPermanent("provider_invalid_result")
        url = media_url(image.get("url"))
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
        value = json_object(response.body) if response.body else {}
        if response.status == 400 and value.get("status") == "ALREADY_COMPLETED":
            return "completed"
        if response.status == 404 and value.get("status") == "NOT_FOUND":
            return "missing"
        raise FalPermanent("provider_cancel_rejected")


__all__ = [
    "APP_ID", "CONNECTION_ID", "CREDENTIAL_REF", "MAX_JSON", "PROVIDER", "QUEUE_ORIGIN",
    "FalAdapter", "FalAuthRequired", "FalError", "FalHandle", "FalImage", "FalPermanent",
    "FalRejected", "FalRequestMissing", "FalSettings", "FalStatus", "FalSubmissionUnknown",
    "FalTransient", "HttpResponse", "UrlLibTransport",
]
