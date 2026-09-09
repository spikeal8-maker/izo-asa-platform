"""ADMIN-001 DTOs. No arbitrary role, price, secret or negative adjustment input."""
import re
from uuid import UUID, uuid5, NAMESPACE_URL
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from ..credits.schemas import PositiveAmount, Entry


class CompensationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    operation_id: UUID
    case_reference: str = Field(min_length=3, max_length=64)
    amount: PositiveAmount
    current_password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("operation_id")
    @classmethod
    def valid_operation(cls, value):
        if value.int == 0:
            raise ValueError("Nonzero operation ID required")
        return value

    @field_validator("case_reference")
    @classmethod
    def normalize_case(cls, value):
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,63}", value):
            raise ValueError("Use a stable case reference without personal data")
        return value

    def case_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, "izo-asa:relaunch-compensation:v1:" + self.case_reference)


class AdminUser(BaseModel):
    id: UUID
    public_code: str
    display_name: str
    state: str
    verified: bool
    created_at: int


class AdminUsers(BaseModel):
    users: list[AdminUser]
    next_after: UUID | None


class AdminAccess(BaseModel):
    permissions: list[str]
    max_grant: int
    csrf_token: str


class CompensationReceipt(BaseModel):
    account_id: UUID
    case_reference: str
    entry: Entry


class AdminEvent(BaseModel):
    id: UUID
    actor_id: UUID
    target_id: UUID | None
    action: str
    outcome: Literal["success", "denied"]
    case_reference: str | None
    operation_id: UUID | None
    created_at: int


class AdminEvents(BaseModel):
    events: list[AdminEvent]
    next_before: UUID | None
