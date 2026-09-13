"""One-time system trial credit. No staff actor, no public grant surface."""
from uuid import UUID, uuid5

import sqlalchemy as sa
from pydantic import ConfigDict, Field

from ..accounts import credit_access as access
from ..accounts import tables as account_tables
from . import repository as repo
from .schemas import Command, CreditError, Entry


class TrialGrant(Command):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    amount: int = Field(strict=True, ge=1, le=3)


def seed_guest_trial(conn, account_id: UUID, amount: int, now: int) -> Entry:
    """Seed exactly one auditable trial allocation for a verified guest identity."""
    states = access.locked_states(conn, [account_id])
    if states.get(account_id) != "active":
        raise CreditError(403, "account_restricted")
    verified_guest = conn.execute(sa.select(account_tables.identities.c.id).where(
        account_tables.identities.c.account_id == account_id,
        account_tables.identities.c.provider == "guest",
        account_tables.identities.c.verified_at.is_not(None))).first()
    if verified_guest is None:
        raise CreditError(403, "guest_required")
    command = TrialGrant(operation_id=uuid5(account_id, "guest-trial-credit"), amount=amount)
    digest = repo.fingerprint("trial", command)
    old = repo.replay(conn, account_id, command.operation_id, digest)
    if old is not None:
        return old
    row = repo.wallet(conn, account_id, create=True)
    return repo.append(conn, row, command, digest, "trial", command.amount, 0, now,
                       reason="guest_trial")
