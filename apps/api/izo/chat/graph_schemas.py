"""Bounded Graph projection; physical message/history DTOs remain compatible."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .schemas import MAX_INPUT_CHARS, MessageView, RequestCreate, RequestView, StrictInput, ThreadView
from .schemas import ThreadDetail as PhysicalThreadDetail

GRAPH_TURN_LIMIT = 50
GRAPH_ATTEMPT_LIMIT = 20
BRANCH_PAGE_LIMIT = 50


class ThreadDetail(PhysicalThreadDetail):
    graph_version: Literal[1] = 1


class GraphAttemptView(BaseModel):
    id: UUID
    turn_id: UUID
    request_id: UUID
    ordinal: int
    model: str
    state: str
    error_code: str | None
    message: MessageView
    created_at: int
    updated_at: int


class GraphTurnView(BaseModel):
    id: UUID
    turn_sequence: int
    assistant_display_sequence: int
    user_message: MessageView
    selected_attempt_id: UUID | None
    selected_attempt: GraphAttemptView | None
    latest_attempt: GraphAttemptView | None
    completed_count: int
    selected_completed_position: int | None
    previous_completed_attempt_id: UUID | None
    next_completed_attempt_id: UUID | None


class GraphPage(BaseModel):
    thread: ThreadView
    active_branch_id: UUID
    revision: int
    turns: list[GraphTurnView]
    next_before_turn_sequence: int | None
    active_attempt: GraphAttemptView | None
    unknown_request_id: UUID | None


class GraphTurnState(BaseModel):
    thread_id: UUID
    active_branch_id: UUID
    revision: int
    turn: GraphTurnView


class GraphAttemptPage(GraphTurnState):
    attempts: list[GraphAttemptView]
    next_before_ordinal: int | None


class GraphRequestAccepted(GraphTurnState):
    execution_branch_id: UUID
    request: RequestView


class GraphRegenerate(StrictInput):
    request_id: UUID
    branch_id: UUID
    source_attempt_id: UUID
    expected_revision: int = Field(ge=0, le=9223372036854775807)


class GraphSelection(StrictInput):
    branch_id: UUID
    attempt_id: UUID
    expected_revision: int = Field(ge=0, le=9223372036854775807)


class BranchView(BaseModel):
    id: UUID
    parent_branch_id: UUID | None
    fork_from_turn_id: UUID | None
    branch_ordinal: int = Field(ge=1, le=9223372036854775807)
    created_at: int


class BranchPage(BaseModel):
    thread_id: UUID
    active_branch_id: UUID
    active_branch: BranchView
    revision: int
    branches: list[BranchView]
    next_before_branch_ordinal: int | None


class BranchEdit(GraphRegenerate):
    text: str = Field(max_length=MAX_INPUT_CHARS)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return RequestCreate.clean_text(value)


class BranchSelection(StrictInput):
    branch_id: UUID
    target_branch_id: UUID
    expected_revision: int = Field(ge=0, le=9223372036854775807)


class BranchEditView(BaseModel):
    thread_id: UUID
    created_branch: BranchView
    turn_id: UUID
    request: RequestView
    active_branch_id: UUID
    revision: int
