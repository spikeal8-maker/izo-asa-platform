"""Integer ledger/holds in the caller's transaction; never calls a provider.

Mutation methods are INTERNAL server commands, not public APIs. Authorization
of Jobs/executor dispatch and price must happen before invoking reserve/settle.
"""
from contextlib import contextmanager
import time
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ..accounts import credit_access as access
from . import repository as repo, tables as t
from .schemas import (CreditError, Entry, Grant, Reserve, Settle, Release,
                      Overview, Reconciliation, MAX_OPERATION)


@contextmanager
def atomic(conn: Connection):
    if not conn.in_transaction():
        raise RuntimeError("Credits requires an explicit caller transaction")
    if conn.dialect.name not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported credits database")
    try:
        # Also safe if the caller catches a rejected command inside its transaction.
        with conn.begin_nested():
            yield
    except IntegrityError as exc:
        # Unique conflicts fail closed; check failures/FK errors are not disguised.
        state = getattr(exc.orig, "sqlstate", None)
        sqlite_unique = getattr(exc.orig, "sqlite_errorcode", None) in {1555, 2067}
        if state == "23505" or sqlite_unique:
            raise CreditError(409, "credit_conflict") from None
        raise


class CreditService:
    def __init__(self, clock=time.time):
        self.clock = clock

    def now(self) -> int:
        return int(self.clock())

    def _lock(self, conn, account_id, actor_id=None):
        ids = [account_id] if actor_id is None else [account_id, actor_id]
        if any(not isinstance(value, UUID) for value in ids):
            raise CreditError(422, "invalid_account")
        states = access.locked_states(conn, ids)
        if any(value not in states for value in ids):
            raise CreditError(404, "not_found")
        return states

    def grant(self, conn: Connection, account_id: UUID, actor_id: UUID,
              command: Grant, *, grant_limit: int = 0) -> Entry:
        """Server-resolved actor and policy cap only. Disabled by default.

        No CLI accepting a claimed actor/permission and no public grant endpoint.
        ADMIN-001 must derive actor from session, fresh auth and its scoped policy.
        """
        command = Grant.model_validate(command.model_dump())
        with atomic(conn):
            states = self._lock(conn, account_id, actor_id)
            if (states[actor_id] != "active" or not access.may_grant(conn, actor_id, self.now())
                    or type(grant_limit) is not int or not 0 < grant_limit <= MAX_OPERATION
                    or command.amount > grant_limit):
                raise CreditError(403, "grant_forbidden")
            if states[account_id] not in {"active", "generation_suspended"}:
                raise CreditError(403, "account_restricted")
            digest = repo.fingerprint("grant", command, actor_id)
            old = repo.replay(conn, account_id, command.operation_id, digest)
            if old is not None:
                return old
            if conn.execute(sa.select(t.ledger.c.entry_id).where(t.ledger.c.case_id == command.case_id)).first():
                raise CreditError(409, "source_already_used")
            row = repo.wallet(conn, account_id, create=True)
            return repo.append(conn, row, command, digest, "grant", command.amount, 0,
                               self.now(), actor_id=actor_id, case_id=command.case_id, reason=command.reason)

    def reserve(self, conn: Connection, account_id: UUID, command: Reserve) -> Entry:
        command = Reserve.model_validate(command.model_dump())
        with atomic(conn):
            states = self._lock(conn, account_id)
            if states[account_id] != "active":
                raise CreditError(403, "account_restricted")
            if not access.verified(conn, account_id):
                raise CreditError(403, "verification_required")
            digest = repo.fingerprint("reserve", command)
            old = repo.replay(conn, account_id, command.operation_id, digest)
            if old is not None:
                return old
            row = repo.wallet(conn, account_id, create=True)
            if command.amount > row["balance"] - row["reserved"]:
                raise CreditError(409, "insufficient_credits")
            conn.execute(sa.insert(t.reservations).values(id=command.reservation_id,
                account_id=account_id, request_id=command.request_id, amount=command.amount,
                state="active", created_at=self.now()))
            return repo.append(conn, row, command, digest, "reserve", 0, command.amount,
                               self.now(), reservation_id=command.reservation_id)

    def settle(self, conn: Connection, account_id: UUID, command: Settle) -> Entry:
        return self._finish(conn, account_id, Settle.model_validate(command.model_dump()), "settle")

    def release(self, conn: Connection, account_id: UUID, command: Release) -> Entry:
        return self._finish(conn, account_id, Release.model_validate(command.model_dump()), "release")

    def _finish(self, conn: Connection, account_id: UUID, command, kind: str) -> Entry:
        with atomic(conn):
            # Closing existing obligations is allowed even after a security lock.
            # This is INTERNAL only; an untrusted browser/worker cannot call it.
            self._lock(conn, account_id)
            digest = repo.fingerprint(kind, command)
            old = repo.replay(conn, account_id, command.operation_id, digest)
            if old is not None:
                return old
            row = repo.wallet(conn, account_id)
            hold = conn.execute(sa.select(t.reservations).where(t.reservations.c.id == command.reservation_id,
                    t.reservations.c.account_id == account_id).with_for_update()).mappings().first()
            if row is None or hold is None:
                raise CreditError(404, "not_found")
            if hold["state"] != "active":
                raise CreditError(409, "reservation_closed")
            charged = command.amount if kind == "settle" else 0
            if charged > hold["amount"]:
                raise CreditError(409, "reservation_exceeded")
            now = self.now()
            conn.execute(sa.update(t.reservations).where(t.reservations.c.id == hold["id"])
                .values(state="settled" if kind == "settle" else "released", charged=charged, closed_at=now))
            return repo.append(conn, row, command, digest, kind, -charged, -hold["amount"],
                               now, reservation_id=hold["id"])

    def overview(self, conn: Connection, account_id: UUID, *, limit: int = 20,
                 before: int | None = None) -> Overview:
        """Account ID MUST come from verified server identity, never a request body."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CreditError(422, "invalid_pagination")
        if before is not None and (type(before) is not int or not 1 <= before <= 9_000_000_000_000):
            raise CreditError(422, "invalid_pagination")
        with atomic(conn):
            states = self._lock(conn, account_id)
            if states[account_id] not in {"active", "generation_suspended"}:
                raise CreditError(403, "account_restricted")
            row = repo.wallet(conn, account_id)
            query = sa.select(t.ledger).where(t.ledger.c.account_id == account_id)
            if before is not None:
                query = query.where(t.ledger.c.sequence < before)
            rows = conn.execute(query.order_by(t.ledger.c.sequence.desc()).limit(limit + 1)).mappings().all()
            entries = [Entry.model_validate(dict(item)) for item in rows[:limit]]
            return Overview(account_id=account_id, balance=repo.balance(row), entries=entries,
                            next_before=entries[-1].sequence if len(rows) > limit else None)

    def reconcile(self, conn: Connection, account_id: UUID) -> Reconciliation:
        """Operator diagnostic only. Detects drift, never silently repairs history."""
        with atomic(conn):
            self._lock(conn, account_id)
            current = repo.balance(repo.wallet(conn, account_id))
            total, reserved, count, seq = conn.execute(sa.select(
                sa.func.coalesce(sa.func.sum(t.ledger.c.balance_delta), 0),
                sa.func.coalesce(sa.func.sum(t.ledger.c.reserved_delta), 0),
                sa.func.count(), sa.func.coalesce(sa.func.max(t.ledger.c.sequence), 0))
                .where(t.ledger.c.account_id == account_id)).one()
            active = conn.execute(sa.select(sa.func.coalesce(sa.func.sum(t.reservations.c.amount), 0))
                .where(t.reservations.c.account_id == account_id, t.reservations.c.state == "active")).scalar_one()
            return Reconciliation(consistent=(total == current.balance and
                reserved == current.reserved == active and count == seq == current.sequence),
                ledger_balance=total, ledger_reserved=reserved, active_reservations=active,
                ledger_entries=count, wallet=current)
