"""Public intents cannot supply price, owner, executor, output key or lease."""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

State = Literal["queued", "claimed", "running", "uploading", "reconciling", "succeeded", "failed", "cancelled"]
ACTIVE = ("queued", "claimed", "running", "uploading", "reconciling")
TERMINAL = ("succeeded", "failed", "cancelled")


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always",
                              hide_input_in_errors=True)


class QuoteInput(JobInput):
    capability_id: Literal["test.image.v1"]
    prompt: str = Field(min_length=1, max_length=2000)
    width: int = Field(strict=True, ge=32, le=512)
    height: int = Field(strict=True, ge=32, le=512)

    @field_validator("prompt")
    @classmethod
    def safe_prompt(cls, value):
        if not value.strip() or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Invalid prompt")
        return value


class CreateJob(JobInput):
    quote_id: UUID
    operation_id: UUID

    @field_validator("quote_id", "operation_id")
    @classmethod
    def nonzero(cls, value):
        if value.int == 0:
            raise ValueError("A nonzero ID is required")
        return value


class CancelJob(JobInput):
    pass


class QuoteView(BaseModel):
    id: UUID
    capability_id: str
    prompt: str
    width: int
    height: int
    credits: int
    expires_at: int
    test_only: Literal[True] = True
    notice: str = "Тестовый исполнитель, не AI-модель. Расходуются тестовые баллы."


class JobView(BaseModel):
    id: UUID
    status: State
    capability_id: str
    prompt: str
    width: int
    height: int
    reserved_credits: int
    charged_credits: int
    asset_id: UUID | None
    error_code: str | None
    cancel_requested: bool
    created_at: int
    updated_at: int
    attempt_count: int
    test_only: Literal[True] = True


class JobList(BaseModel):
    jobs: list[JobView]
    next_offset: int | None


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    account_id: UUID
    attempt_id: UUID
    fence: int


class JobError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code
