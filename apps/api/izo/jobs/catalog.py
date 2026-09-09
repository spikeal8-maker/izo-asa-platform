"""Closed test adapter configuration. No URL, key or arbitrary workflow inputs."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from .schemas import JobError

CAPABILITY = "test.image.v1"
POOL = "api:test.image.v1"
PRICE = 1
VERSION = "test-image-1"


class JobSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_JOBS_", extra="ignore", hide_input_in_errors=True)
    enabled: bool = False
    lease_seconds: int = Field(default=30, ge=10, le=300)
    deadline_seconds: int = Field(default=900, ge=600, le=3600)
    max_attempts: int = Field(default=3, ge=1, le=5)

    def require_enabled(self):
        if not self.enabled:
            raise JobError(503, "jobs_disabled")


def output_bound(width: int, height: int) -> int:
    return width * height * 4 + max(width, height) * 8 + 65536
