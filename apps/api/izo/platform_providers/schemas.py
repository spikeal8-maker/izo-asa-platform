"""Strict write-only server-provider configuration DTOs."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from typing import Literal

class StrictCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

class ProviderView(BaseModel):
    provider: Literal["deepseek"] = "deepseek"
    configured: bool
    enabled: bool
    verified: bool
    status: Literal["not_configured", "not_verified", "disabled", "verified"]
    model: Literal["deepseek-flash", "deepseek-v4-pro"]
    revision: int | None
    generation: int | None
    daily_limit: int
    concurrency_limit: int
    # Next package implements admission, budget and execution. Never claim otherwise.
    available_to_users: bool = False

class ProviderList(BaseModel):
    connections: list[ProviderView]

class ReplaceKey(StrictCommand):
    operation_id: UUID
    expected_revision: int | None = Field(default=None, ge=1)
    key: SecretStr = Field(min_length=8, max_length=512)
    current_password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: SecretStr):
        text = value.get_secret_value()
        if text != text.strip() or any(ord(c) < 33 or ord(c) > 126 for c in text):
            raise ValueError("Key must contain printable ASCII without whitespace")
        return value

class VerifyKey(StrictCommand):
    operation_id: UUID
    expected_revision: int = Field(ge=1)
    current_password: SecretStr = Field(min_length=1, max_length=128)

class UpdatePolicy(StrictCommand):
    operation_id: UUID
    expected_revision: int = Field(ge=1)
    enabled: bool
    model: Literal["deepseek-flash", "deepseek-v4-pro"]
    daily_limit: int = Field(ge=1, le=200, strict=True)
    concurrency_limit: int = Field(ge=1, le=10, strict=True)
    current_password: SecretStr = Field(min_length=1, max_length=128)
