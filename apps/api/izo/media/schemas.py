"""Image upload intent and owner-safe responses; no object paths or caller identity."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_INPUT = 16 * 1024 * 1024
MAX_OUTPUT = 65 * 1024 * 1024
MAX_PIXELS = 16_777_216


class MediaInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True,
                             revalidate_instances="always")


class UploadIntent(MediaInput):
    operation_id: UUID
    content_type: Literal["image/png", "image/jpeg", "image/webp"]
    byte_size: int = Field(strict=True, ge=1, le=MAX_INPUT)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: int = Field(strict=True, ge=1, le=8192)
    height: int = Field(strict=True, ge=1, le=8192)

    @model_validator(mode="after")
    def pixel_bound(self):
        if self.width * self.height > MAX_PIXELS:
            raise ValueError("Image pixel budget exceeded")
        return self

    def storage_bound(self) -> int:
        # RGBA output, scanline/compression overhead and headers. The encoder
        # enforces this bound too; it is a reservation, not a size prediction.
        return min(MAX_OUTPUT, self.width * self.height * 4 + max(self.width, self.height) * 8 + 65536)


class EmptyCommand(MediaInput):
    pass


class UploadView(BaseModel):
    id: UUID
    status: Literal["pending", "validating", "storing", "ready", "rejected", "expired", "cancelled"]
    expires_at: int
    reserved_bytes: int
    asset_id: UUID | None = None


class AssetView(BaseModel):
    id: UUID
    kind: Literal["image"] = "image"
    content_type: Literal["image/png"] = "image/png"
    byte_size: int
    width: int
    height: int
    sha256: str
    created_at: int


class AssetList(BaseModel):
    assets: list[AssetView]
    next_offset: int | None
    used_bytes: int
    reserved_bytes: int


class DownloadView(BaseModel):
    url: str
    expires_at: int


class MediaError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code
