"""Bounded server-owned policy for the first DeepSeek text preview."""
from __future__ import annotations

import base64
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL_REVISION = "deepseek-2026-09-d1"
MODELS = (
    ("deepseek-flash", "DeepSeek Flash"),
    ("deepseek-v4-pro", "DeepSeek V4 Pro"),
)
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
        env_prefix="IZO_CHAT_", extra="ignore", hide_input_in_errors=True
    )
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
