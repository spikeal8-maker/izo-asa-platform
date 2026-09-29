"""Fal constants, settings and small value/error types."""
from dataclasses import dataclass
import math
from typing import Mapping

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
    """Known request can be retried without regenerating."""


class FalAuthRequired(FalError):
    """Known request needs operator credential intervention, not failover."""


class FalPermanent(FalError):
    """Provider returned a permanent invalid response for a known request."""


class FalRequestMissing(FalPermanent):
    """A known request is no longer pollable."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


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
