"""SETTINGS-002 contracts. No free-form JSON and no secret fields."""
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..entitlements.schemas import PlanPolicy


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                             revalidate_instances="always", hide_input_in_errors=True)


class SettingDescriptor(StrictModel):
    id: str
    key: str
    value_type: str
    apply_mode: Literal["V"] = "V"
    required_when_generation_enabled: bool
    default_semantics: str


class DiffItem(StrictModel):
    key: str
    before: Any
    after: Any


class BasicSettingsView(StrictModel):
    default_version: int
    revision_id: UUID | None
    revision: int | None
    policy_hash: str | None
    policy: PlanPolicy
    generation_enabled: bool
    descriptors: tuple[SettingDescriptor, ...]


class PreviewInput(StrictModel):
    expected_revision: int = Field(strict=True, ge=0, le=2_000_000_000)
    policy: PlanPolicy

    @field_validator("policy", mode="before")
    @classmethod
    def policy_from_http_json(cls, value):
        if isinstance(value, PlanPolicy) or not isinstance(value, dict):
            return value
        return PlanPolicy.model_validate_json(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


class PreviewView(StrictModel):
    expected_revision: int
    current_revision: int
    diff: tuple[DiffItem, ...]
    generation_enabled: bool
    missing_required: tuple[str, ...]
    impact: tuple[str, ...]


class PublishInput(PreviewInput):
    operation_id: UUID

    @field_validator("operation_id", mode="before")
    @classmethod
    def operation_id_from_http_json(cls, value):
        if isinstance(value, UUID) or not isinstance(value, str):
            return value
        try:
            return UUID(value)
        except ValueError:
            return value
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def reason_is_meaningful(self):
        if not self.reason.strip() or any(ord(c) < 32 for c in self.reason):
            raise ValueError("Reason required")
        return self


class RollbackInput(StrictModel):
    operation_id: UUID

    @field_validator("operation_id", mode="before")
    @classmethod
    def operation_id_from_http_json(cls, value):
        if isinstance(value, UUID) or not isinstance(value, str):
            return value
        try:
            return UUID(value)
        except ValueError:
            return value
    expected_revision: int = Field(strict=True, ge=0, le=2_000_000_000)
    target_revision: int = Field(strict=True, ge=1, le=2_000_000_000)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def reason_is_meaningful(self):
        if not self.reason.strip() or any(ord(c) < 32 for c in self.reason):
            raise ValueError("Reason required")
        return self


class PublishReceipt(StrictModel):
    operation_id: UUID
    default_version: int
    revision_id: UUID
    revision: int
    policy_hash: str
    action: Literal["publish", "rollback"]


class HistoryItem(StrictModel):
    revision_id: UUID
    revision: int
    policy_hash: str
    created_at: int
    active: bool
    policy: PlanPolicy


class HistoryView(StrictModel):
    items: tuple[HistoryItem, ...]


class SettingsError(Exception):
    def __init__(self, status: int, code: str, fields: tuple[str, ...] = ()):
        super().__init__(code)
        self.status, self.code, self.fields = status, code, fields
