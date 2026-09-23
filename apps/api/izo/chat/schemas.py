"""Public Chat DTOs: no provider secret, endpoint, ciphertext or raw response."""
from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from .settings import MAX_INPUT_CHARS

class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

class ModelView(BaseModel):
    id: str
    label: str

class ChatPolicyView(BaseModel):
    revision: str
    default_model: str
    models: list[ModelView]
    max_input_chars: int
    max_output_tokens: int

class CredentialView(BaseModel):
    configured: bool
    enabled: bool
    verified: bool
    revision: int | None = None
    generation: int | None = None
    provider: str = "deepseek"

class CredentialWrite(StrictInput):
    operation_id: UUID
    key: SecretStr = Field(min_length=8, max_length=512)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("key")
    @classmethod
    def clean_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw != raw.strip() or "\x00" in raw or any(ord(c) < 33 or ord(c) > 126 for c in raw):
            raise ValueError("Invalid credential")
        return value

class CredentialCommand(StrictInput):
    operation_id: UUID
    expected_revision: int = Field(ge=1)

class ThreadCreate(StrictInput):
    title: str | None = Field(default=None, max_length=120)

class ThreadView(BaseModel):
    id: UUID
    title: str
    created_at: int
    updated_at: int

class ThreadList(BaseModel):
    threads: list[ThreadView]

class MessageView(BaseModel):
    id: UUID
    request_id: UUID
    role: str
    sequence: int
    content: str
    state: str
    created_at: int
    updated_at: int

class ThreadDetail(BaseModel):
    thread: ThreadView
    messages: list[MessageView]

class RequestCreate(StrictInput):
    request_id: UUID
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    model: str = Field(min_length=1, max_length=64)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Invalid message")
        return value

class RequestView(BaseModel):
    id: UUID
    thread_id: UUID
    model: str
    state: str
    error_code: str | None
    created_at: int
    updated_at: int
    deadline_at: int
