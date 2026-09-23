"""Public Chat DTOs: no provider secret, endpoint, ciphertext or raw response."""
from __future__ import annotations

import base64
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL_REVISION = "deepseek-2026-09-d1"
MODELS = (("deepseek-flash", "DeepSeek Flash"), ("deepseek-v4-pro", "DeepSeek V4 Pro"))
DEFAULT_MODEL = MODELS[0][0]
MAX_INPUT_CHARS = 6_000
MAX_CONTEXT_MESSAGES = 40
MAX_CONTEXT_CHARS = 24_000
MAX_OUTPUT_TOKENS = 2_048
MAX_ASSISTANT_CHARS = 64_000
MAX_SSE_LINE = 256 * 1024
REQUEST_WINDOW_SECONDS = 300
REQUEST_WINDOW_LIMIT = 20
CREDENTIAL_WINDOW_LIMIT = 6
THREAD_PAGE_LIMIT = 50
MESSAGE_PAGE_LIMIT = 100

class ChatSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IZO_CHAT_", extra="ignore", hide_input_in_errors=True)
    root_key: SecretStr = SecretStr("")
    preview_account_emails: str = "preview@local.izo"
    request_deadline_seconds: int = Field(default=75, ge=10, le=180)

    def root_key_bytes(self) -> bytes:
        raw = self.root_key.get_secret_value().strip()
        try:
            value = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        except (ValueError, TypeError):
            value = b""
        if len(value) != 32:
            raise RuntimeError("chat credential root key is not configured")
        return value

    def admitted(self, email: str | None) -> bool:
        allowed = {item.strip().lower() for item in self.preview_account_emails.split(",")}
        return bool(email and email.lower() in allowed)

    @staticmethod
    def model_allowed(model: str) -> bool:
        return any(model == model_id for model_id, _ in MODELS)

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
