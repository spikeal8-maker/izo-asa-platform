"""Finite image capability catalog. Prices are product credits, never provider cost."""
from dataclasses import dataclass
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from .schemas import JobError

TEST_CAPABILITY = "test.image.v1"
FAL_CAPABILITY = "fal.flux2.klein.4b"
TEST_POOL = "api:test.image.v1"
FAL_POOL = "api:fal.flux2.klein.4b"


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    pool: str
    credits: int
    version: str
    test_only: bool
    external: bool
    notice: str


CAPABILITIES = {
    TEST_CAPABILITY: CapabilitySpec(
        id=TEST_CAPABILITY,
        pool=TEST_POOL,
        credits=1,
        version="test-image-1",
        test_only=True,
        external=False,
        notice="Тестовый исполнитель, не AI-модель. Расходуются тестовые баллы.",
    ),
    FAL_CAPABILITY: CapabilitySpec(
        id=FAL_CAPABILITY,
        pool=FAL_POOL,
        credits=1,
        version="fal-klein4b-1",
        test_only=False,
        external=True,
        notice="Реальная AI-генерация через fal.ai. Перед запуском сервер проверяет план и лимит провайдера.",
    ),
}

# Compatibility aliases for the existing isolated test executor and acceptance tools.
CAPABILITY = TEST_CAPABILITY
POOL = TEST_POOL
PRICE = CAPABILITIES[TEST_CAPABILITY].credits
VERSION = CAPABILITIES[TEST_CAPABILITY].version


class JobSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IZO_JOBS_", extra="ignore", hide_input_in_errors=True)
    enabled: bool = False
    lease_seconds: int = Field(default=30, ge=10, le=300)
    deadline_seconds: int = Field(default=900, ge=600, le=3600)
    max_attempts: int = Field(default=3, ge=1, le=5)

    def require_enabled(self):
        if not self.enabled:
            raise JobError(503, "jobs_disabled")


def capability(capability_id: str) -> CapabilitySpec:
    try:
        return CAPABILITIES[capability_id]
    except KeyError:
        raise JobError(409, "capability_unsupported") from None


def output_bound(width: int, height: int) -> int:
    return width * height * 4 + max(width, height) * 8 + 65536
