"""Typed policy, internal commands and public own-plan view. No secret fields."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]
Bytes = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000_000)]
Credits = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
Epoch = Annotated[int, Field(strict=True, ge=0, le=253402300799)]
Version = Annotated[int, Field(strict=True, ge=0, le=2_000_000_000)]
CapabilityId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")]
Executor = Literal["api", "local"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                             revalidate_instances="always", hide_input_in_errors=True)


class ImageSize(StrictModel):
    width: int = Field(strict=True, ge=1, le=8192)
    height: int = Field(strict=True, ge=1, le=8192)


class PlanPolicy(StrictModel):
    # Empty/zero defaults DENY. These are safety bounds, not commercial plans.
    capability_ids: tuple[CapabilityId, ...] = Field(default=(), max_length=256)
    executors: tuple[Executor, ...] = Field(default=(), max_length=2)
    active_jobs: int = Field(default=0, strict=True, ge=0, le=256)
    submissions: Count = 0
    window_seconds: int = Field(default=60, strict=True, ge=1, le=86400)
    storage_bytes: Bytes = 0
    upload_bytes: int = Field(default=0, strict=True, ge=0, le=1_000_000_000)
    input_count: int = Field(default=0, strict=True, ge=0, le=32)
    image_sizes: tuple[ImageSize, ...] = Field(default=(), max_length=32)
    max_action_credits: Credits = 0
    can_publish: bool = False

    @model_validator(mode="after")
    def coherent(self):
        for values in (self.capability_ids, self.executors, self.image_sizes):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate policy values")
        if self.upload_bytes > self.storage_bytes:
            raise ValueError("Upload limit exceeds total storage")
        return self


class Command(StrictModel):
    operation_id: UUID
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def meaningful_reason(self):
        if not self.reason.strip() or any(ord(c) < 32 for c in self.reason):
            raise ValueError("Reason required")
        return self


class PublishPlan(Command):
    revision_id: UUID
    plan_code: Literal["basic", "extended", "custom"]
    revision: int = Field(strict=True, ge=1, le=2_000_000_000)
    policy: PlanPolicy


class SetDefault(Command):
    revision_id: UUID
    expected_version: Version


class AssignPlan(Command):
    revision_id: UUID | None
    expected_version: Version
    starts_at: Epoch | None = None
    expires_at: Epoch | None = None

    @model_validator(mode="after")
    def period(self):
        if self.revision_id is None:
            if self.starts_at is not None or self.expires_at is not None:
                raise ValueError("Clearing an assignment has no dates")
        elif self.starts_at is None or (self.expires_at is not None and self.expires_at <= self.starts_at):
            raise ValueError("Invalid assignment period")
        return self


class ChangeReceipt(StrictModel):
    operation_id: UUID
    action: Literal["publish", "default", "assign"]
    revision_id: UUID | None
    target_id: UUID | None
    version: Version


class EntitlementView(StrictModel):
    account_id: UUID
    account_state: str
    identity_verified: bool
    configured: bool
    source: Literal["none", "basic", "assignment"]
    assignment_state: Literal["none", "scheduled", "active", "expired"]
    assignment_version: Version
    default_version: Version
    revision_id: UUID | None
    plan_code: str | None
    revision: int | None
    policy_hash: str | None
    policy: PlanPolicy | None
    as_of: Epoch
    next_change_at: Epoch | None


class EntitlementError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code
