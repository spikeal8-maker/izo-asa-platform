"""Public Chat DTOs: no provider secret, endpoint, ciphertext, object key or raw response."""
from __future__ import annotations

import base64
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderId = Literal["deepseek", "openrouter"]
MODEL_REVISION = "multi-provider-2026-09-1"
# public id, label, provider, provider model, text, vision, description
MODELS = (
    ("deepseek-flash", "DeepSeek Flash", "deepseek", "deepseek-flash",
     True, True, "Текст · Изображения"),
    ("deepseek-v4-pro", "DeepSeek V4 Pro", "deepseek", "deepseek-v4-pro",
     True, False, "Текст"),
    ("openrouter-auto", "OpenRouter Auto", "openrouter", "openrouter/auto",
     True, False, "Текст"),
)
PROVIDERS: tuple[ProviderId, ...] = ("deepseek", "openrouter")
DEFAULT_MODEL = MODELS[0][0]
MAX_INPUT_CHARS = 6_000
MAX_CONTEXT_MESSAGES = 40
MAX_CONTEXT_CHARS = 24_000
MAX_OUTPUT_TOKENS = 2_048
MAX_ASSISTANT_CHARS = 64_000
MAX_SSE_LINE = 256 * 1024
MAX_CHAT_ATTACHMENTS = 5
MAX_CHAT_IMAGE_BYTES = 12 * 1024 * 1024
MAX_CONTEXT_IMAGE_BYTES = 24 * 1024 * 1024
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
    local_preview_enabled: bool = False
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
    def provider_allowed(provider: str) -> bool:
        return provider in PROVIDERS

    @staticmethod
    def model_spec(model: str):
        return next((item for item in MODELS if item[0] == model), None)

    @classmethod
    def model_allowed(cls, model: str) -> bool:
        return cls.model_spec(model) is not None

    @classmethod
    def model_provider(cls, model: str) -> ProviderId | None:
        spec = cls.model_spec(model)
        return spec[2] if spec else None

    @classmethod
    def provider_model(cls, model: str) -> str | None:
        spec = cls.model_spec(model)
        return spec[3] if spec else None

    @classmethod
    def model_supports_vision(cls, model: str) -> bool:
        spec = cls.model_spec(model)
        return bool(spec and spec[5])


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class ModelView(BaseModel):
    id: str
    label: str
    provider: ProviderId
    text: bool
    vision: bool
    description: str


class ChatPolicyView(BaseModel):
    revision: str
    default_model: str
    models: list[ModelView]
    max_input_chars: int
    max_output_tokens: int
    max_image_bytes: int
    max_attachments: int


class CredentialView(BaseModel):
    configured: bool
    enabled: bool
    verified: bool
    revision: int | None = None
    generation: int | None = None
    provider: ProviderId = "deepseek"


class CredentialListView(BaseModel):
    credentials: list[CredentialView]


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


class AttachmentView(BaseModel):
    id: UUID
    asset_id: UUID
    media_type: Literal["image/png"]
    byte_size: int
    width: int
    height: int
    sha256: str
    created_at: int


class MessageView(BaseModel):
    id: UUID
    request_id: UUID
    role: str
    sequence: int
    content: str
    state: str
    attachments: list[AttachmentView] = Field(default_factory=list)
    created_at: int
    updated_at: int


class ThreadDetail(BaseModel):
    thread: ThreadView
    messages: list[MessageView]


class RequestCreate(StrictInput):
    request_id: UUID
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    model: str = Field(min_length=1, max_length=64)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=MAX_CHAT_ATTACHMENTS)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Invalid message")
        return value

    @field_validator("attachment_ids")
    @classmethod
    def unique_attachments(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate attachment")
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
