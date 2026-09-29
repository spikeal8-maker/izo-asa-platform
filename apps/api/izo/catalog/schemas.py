"""Strict catalog DTOs: kopeks are display metadata, never a debit."""
import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_PRICE = 1_000_000_000_000
PRICE_COLUMNS = ("input_kopeks_per_million", "output_kopeks_per_million", "image_kopeks_per_image")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Price(StrictModel):
    currency: Literal["RUB"] = "RUB"
    input_kopeks_per_million: int | None = Field(default=None, ge=0, le=MAX_PRICE, strict=True)
    output_kopeks_per_million: int | None = Field(default=None, ge=0, le=MAX_PRICE, strict=True)
    image_kopeks_per_image: int | None = Field(default=None, ge=0, le=MAX_PRICE, strict=True)

    @classmethod
    def from_row(cls, row):
        return cls(**{name: row[name] for name in PRICE_COLUMNS})


class ProviderView(BaseModel):
    id: str
    label: str


class ModelView(BaseModel):
    id: str
    provider: str
    modality: Literal["text", "image"]
    label: str
    published: bool
    enabled: bool
    is_default: bool
    publishable: bool
    price_source: Literal["unset", "admin_manual"]
    updated_at: int
    price: Price


class CatalogView(BaseModel):
    revision: int
    permissions: list[str]
    providers: list[ProviderView]
    models: list[ModelView]


class CatalogPatch(StrictModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, le=2_000_000_000, strict=True)
    published: bool = Field(strict=True)
    enabled: bool = Field(strict=True)
    is_default: bool = Field(strict=True)
    price: Price
    reason: str = Field(min_length=3, max_length=300)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3 or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid catalog reason")
        return value

    def fingerprint(self, model_id: str) -> str:
        data = {"model": model_id, "command": self.model_dump(mode="json")}
        raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


APPROVED = (
    ("deepseek-flash", "deepseek", "text", "DeepSeek Flash"),
    ("deepseek-v4-pro", "deepseek", "text", "DeepSeek V4 Pro"),
    ("fal.flux2.klein.4b", "fal", "image", "FLUX.2 Klein 4B"),
)
PROVIDERS = (ProviderView(id="deepseek", label="DeepSeek"),
             ProviderView(id="fal", label="fal.ai"))
