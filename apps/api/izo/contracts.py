"""Provider-neutral DTOs; no database, HTTP framework or provider implementation."""
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Modality(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    THREE_D = "3d"
    CHAT = "chat"


class Executor(StrEnum):
    API = "api"
    LOCAL = "local"


class JobState(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    UPLOADING = "uploading"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONCILING = "reconciling"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Capability(Contract):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    modality: Modality
    enabled: bool = False
    provider_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    executor: Executor
    input_modalities: tuple[Modality, ...] = ()
    max_inputs: int = Field(default=0, ge=0, le=32)


class JobSpec(Contract):
    """Internal server-owned contract, NOT a public create-job request."""
    schema_version: Literal[1] = 1
    id: UUID
    owner_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=100)
    capability_id: str = Field(min_length=1, max_length=80)
    modality: Modality
    executor: Executor
    provider_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    input_asset_ids: tuple[UUID, ...] = Field(default=(), max_length=32)
    prompt: str = Field(default="", max_length=32000)
    reserved_credits: int = Field(default=0, ge=0, strict=True)


class AssetRef(Contract):
    id: UUID
    owner_id: UUID
    modality: Modality
    object_key: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=0)
    visibility: Literal["private"] = "private"
