"""ACCESS-001 strict contracts; passwords and actor identity never appear in receipts."""
import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from .permissions import KNOWN_GLOBAL, MIN_DELEGATED_SECONDS, MAX_DELEGATED_SECONDS


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class AccessMutation(StrictInput):
    operation_id: UUID
    permission: str = Field(min_length=3, max_length=80)
    scope: Literal["global"] = "global"
    case_reference: str = Field(min_length=3, max_length=64)
    current_password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("operation_id")
    @classmethod
    def valid_operation(cls, value):
        if value.int == 0:
            raise ValueError("Nonzero operation ID required")
        return value

    @field_validator("permission")
    @classmethod
    def known_permission(cls, value):
        if value not in KNOWN_GLOBAL:
            raise ValueError("Unknown global permission")
        return value

    @field_validator("case_reference")
    @classmethod
    def normalize_case(cls, value):
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,63}", value):
            raise ValueError("Use a stable case reference without personal data")
        return value


class GrantAccessInput(AccessMutation):
    ttl_seconds: int = Field(ge=MIN_DELEGATED_SECONDS, le=MAX_DELEGATED_SECONDS, strict=True)


class RevokeAccessInput(AccessMutation):
    pass


class AccessPermission(BaseModel):
    permission: str
    expires_at: int | None
    managed: bool


class AccessSubject(BaseModel):
    id: UUID
    public_code: str
    display_name: str
    state: str
    verified: bool
    permissions: list[AccessPermission]


class AccessMe(BaseModel):
    permissions: list[str]
    delegation_ceiling: list[str]
    csrf_token: str


class AccessReceipt(BaseModel):
    operation_id: UUID
    target_id: UUID
    action: Literal["grant", "revoke"]
    permission: str
    scope: Literal["global"]
    expires_at: int | None
    case_reference: str
