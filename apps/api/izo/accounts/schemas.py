"""Public authentication DTOs: caller cannot set owner, role, permissions or money."""
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def normalize_email(value: str) -> str:
    # Deliberate ASCII mailbox subset; SMTPUTF8/quoted local-parts are not supported.
    value = value.strip().lower()
    if len(value) > 254 or not value.isascii() or value.count("@") != 1:
        raise ValueError("Invalid email")
    local, domain = value.split("@")
    if (not 1 <= len(local) <= 64 or local.startswith(".") or local.endswith(".")
            or ".." in local or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)):
        raise ValueError("Invalid email")
    labels = domain.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels):
        raise ValueError("Invalid email")
    return value


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class LoginInput(StrictInput):
    email: str = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)
    _email = field_validator("email")(normalize_email)


class RegisterInput(LoginInput):
    password: SecretStr = Field(min_length=15, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    invite_code: SecretStr = Field(min_length=43, max_length=43)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 15 or len(raw.encode("utf-8")) > 512 or "\x00" in raw:
            raise ValueError("Password length must be between 15 and 128 characters")
        return value

    @field_validator("display_name")
    @classmethod
    def name_policy(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid display name")
        return value


class AccountView(BaseModel):
    id: UUID
    public_code: str
    display_name: str
    email: str | None
    email_verified: bool
    state: str
    permissions: list[str]


class SessionView(BaseModel):
    id: UUID
    created_at: int
    last_seen_at: int
    expires_at: int
    client_label: str
    current: bool


class AuthView(BaseModel):
    account: AccountView
    csrf_token: str


class SessionList(BaseModel):
    sessions: list[SessionView]


class ErrorDetail(BaseModel):
    code: str


class AuthErrorView(BaseModel):
    error: ErrorDetail
