"""Typed server commands and safe read DTOs. Units are product credits, not money."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Arithmetic safety bounds, NOT subscription prices or a promised user allowance.
MAX_BALANCE = 9_000_000_000_000
MAX_OPERATION = 1_000_000_000
PositiveAmount = Annotated[int, Field(strict=True, ge=1, le=MAX_OPERATION)]
FinalAmount = Annotated[int, Field(strict=True, ge=0, le=MAX_OPERATION)]


class CreditError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    operation_id: UUID

    @field_validator("operation_id")
    @classmethod
    def nonzero(cls, value: UUID) -> UUID:
        if value.int == 0:
            raise ValueError("A nonzero operation ID is required")
        return value


class Grant(Command):
    amount: PositiveAmount
    case_id: UUID
    reason: Literal["compensation", "test_grant"]


class Reserve(Command):
    reservation_id: UUID
    request_id: UUID
    amount: PositiveAmount


class Settle(Command):
    reservation_id: UUID
    amount: FinalAmount


class Release(Command):
    reservation_id: UUID


class Balance(BaseModel):
    balance: int = 0
    reserved: int = 0
    available: int = 0
    sequence: int = 0


class Entry(BaseModel):
    entry_id: UUID
    operation_id: UUID
    sequence: int
    kind: Literal["grant", "reserve", "settle", "release"]
    balance_delta: int
    reserved_delta: int
    balance_after: int
    reserved_after: int
    reservation_id: UUID | None
    reason: Literal["compensation", "test_grant", "generation"]
    created_at: int


class Overview(BaseModel):
    account_id: UUID
    balance: Balance
    entries: list[Entry]
    next_before: int | None


class Reconciliation(BaseModel):
    consistent: bool
    ledger_balance: int
    ledger_reserved: int
    active_reservations: int
    ledger_entries: int
    wallet: Balance
