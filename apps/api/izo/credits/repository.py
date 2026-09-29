"""Wallet-serialized persistence. Caller owns the transaction and Account locks."""
import hashlib
import json
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from ..accounts import credit_access as access
from . import tables as t
from .schemas import Balance, Command, CreditError, Entry, MAX_BALANCE


def fingerprint(kind: str, command: Command, actor_id: UUID | None = None) -> str:
    payload = {"version": 1, "kind": kind, "command": command.model_dump(mode="json"),
               "actor": str(actor_id) if actor_id else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def wallet(conn: Connection, account_id: UUID, create: bool = False):
    row = conn.execute(sa.select(t.wallets).where(t.wallets.c.account_id == account_id)
                       .with_for_update()).mappings().first()
    if row is None and create:
        # Account is already locked, including the first write when no wallet exists.
        conn.execute(sa.insert(t.wallets).values(account_id=account_id, balance=0, reserved=0, sequence=0))
        return {"account_id": account_id, "balance": 0, "reserved": 0, "sequence": 0}
    return row


def balance(row) -> Balance:
    if row is None:
        return Balance()
    return Balance(balance=row["balance"], reserved=row["reserved"],
                   available=row["balance"] - row["reserved"], sequence=row["sequence"])


def replay(conn: Connection, account_id: UUID, operation_id: UUID, digest: str) -> Entry | None:
    old = conn.execute(sa.select(t.ledger).where(t.ledger.c.account_id == account_id,
                         t.ledger.c.operation_id == operation_id)).mappings().first()
    if old is None:
        return None
    if old["request_hash"] != digest:
        raise CreditError(409, "idempotency_conflict")
    # Exact immutable receipt, NOT a newly calculated current balance.
    return Entry.model_validate(dict(old))


def append(conn: Connection, row, command: Command, digest: str, kind: str,
           balance_delta: int, reserved_delta: int, now: int,
           actor_id: UUID | None = None, case_id: UUID | None = None,
           reservation_id: UUID | None = None, reason: str = "generation") -> Entry:
    total, held = row["balance"] + balance_delta, row["reserved"] + reserved_delta
    if not 0 <= held <= total <= MAX_BALANCE:
        raise CreditError(409, "credit_bounds")
    entry_id, sequence = uuid4(), row["sequence"] + 1
    values = dict(entry_id=entry_id, account_id=row["account_id"], operation_id=command.operation_id,
        request_hash=digest, sequence=sequence, kind=kind, balance_delta=balance_delta,
        reserved_delta=reserved_delta, balance_after=total, reserved_after=held,
        reservation_id=reservation_id, actor_id=actor_id, case_id=case_id, reason=reason, created_at=now)
    conn.execute(sa.insert(t.ledger).values(**values))
    updated = conn.execute(sa.update(t.wallets).where(t.wallets.c.account_id == row["account_id"],
        t.wallets.c.sequence == row["sequence"]).values(balance=total, reserved=held, sequence=sequence))
    if updated.rowcount != 1:
        raise CreditError(409, "credit_version_conflict")
    access.record_event(conn, row["account_id"], kind, entry_id, now)
    return Entry.model_validate(values)
