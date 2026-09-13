"""CREDIT-001 wallet lifecycle, reservation and idempotency invariants."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.accounts import tables as auth_tables
from izo.credits import tables as t
from izo.credits.schemas import Grant, Release, Reserve, Settle
from credit_support import assert_error, credit_env, grant, reserve


def test_empty_wallet_read_is_not_a_grant_or_wallet_creation(credit_env):
    engine, svc, owner, _, _ = credit_env
    with engine.begin() as conn:
        result = svc.overview(conn, owner)
        assert result.balance.available == 0 and result.entries == [] and result.next_before is None
        assert conn.execute(sa.select(sa.func.count()).select_from(t.wallets)).scalar_one() == 0


def test_reserve_and_partial_settlement_arithmetic(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve(70)
        svc.reserve(conn, owner, hold)
        result = svc.overview(conn, owner).balance
        assert (result.balance, result.reserved, result.available) == (100, 70, 30)
        final = svc.settle(conn, owner, Settle(
            operation_id=uuid4(), reservation_id=hold.reservation_id, amount=50))
        assert (final.balance_delta, final.reserved_delta) == (-50, -70)
        result = svc.overview(conn, owner).balance
        assert (result.balance, result.reserved, result.available, result.sequence) == (50, 0, 50, 3)
        assert svc.reconcile(conn, owner).consistent


def test_release_restores_available_without_minting_credits(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve()
        svc.reserve(conn, owner, hold)
        command = Release(operation_id=uuid4(), reservation_id=hold.reservation_id)
        receipt = svc.release(conn, owner, command)
        assert svc.release(conn, owner, command) == receipt
        assert (receipt.balance_delta, receipt.reserved_delta) == (0, -70)
        assert svc.overview(conn, owner).balance.available == 100
        assert svc.reconcile(conn, owner).consistent


@pytest.mark.parametrize("kind", ["grant", "reserve", "settle", "release"])
def test_all_operations_replay_exact_receipt_after_subsequent_changes(credit_env, kind):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        command = Grant(operation_id=uuid4(), amount=100, case_id=uuid4(), reason="compensation")
        first = grant(conn, svc, owner, staff, command=command)
        call = lambda: grant(conn, svc, owner, staff, command=command)
        if kind != "grant":
            hold = reserve(60)
            first = svc.reserve(conn, owner, hold)
            call = lambda: svc.reserve(conn, owner, hold)
            if kind in {"settle", "release"}:
                finish = (Settle(operation_id=uuid4(), reservation_id=hold.reservation_id, amount=40)
                          if kind == "settle" else Release(
                              operation_id=uuid4(), reservation_id=hold.reservation_id))
                first = getattr(svc, kind)(conn, owner, finish)
                call = lambda: getattr(svc, kind)(conn, owner, finish)
        grant(conn, svc, owner, staff, amount=20)
        sequence = svc.overview(conn, owner).balance.sequence
        assert call() == first
        assert svc.overview(conn, owner).balance.sequence == sequence
        assert svc.reconcile(conn, owner).consistent


@pytest.mark.parametrize("kind", ["grant", "reserve", "settle"])
def test_idempotency_key_with_different_payload_is_conflict(credit_env, kind):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        g = Grant(operation_id=uuid4(), amount=100, case_id=uuid4(), reason="test_grant")
        grant(conn, svc, owner, staff, command=g)
        if kind == "grant":
            call = lambda: grant(conn, svc, owner, staff,
                                 command=g.model_copy(update={"amount": 101}))
        else:
            hold = reserve(70)
            svc.reserve(conn, owner, hold)
            if kind == "reserve":
                call = lambda: svc.reserve(conn, owner, hold.model_copy(update={"amount": 50}))
            else:
                end = Settle(operation_id=uuid4(), reservation_id=hold.reservation_id, amount=20)
                svc.settle(conn, owner, end)
                call = lambda: svc.settle(conn, owner, end.model_copy(update={"amount": 21}))
        assert_error("idempotency_conflict", call)
        assert svc.reconcile(conn, owner).consistent


def test_case_cannot_credit_two_accounts_or_new_operation(credit_env):
    engine, svc, owner, other, staff = credit_env
    g = Grant(operation_id=uuid4(), amount=100, case_id=uuid4(), reason="compensation")
    with engine.begin() as conn:
        grant(conn, svc, owner, staff, command=g)
        repeated = g.model_copy(update={"operation_id": uuid4()})
        assert_error("source_already_used", lambda: grant(conn, svc, owner, staff, command=repeated))
        assert_error("source_already_used", lambda: grant(conn, svc, other, staff, command=repeated))
        assert svc.overview(conn, other).balance.available == 0


def test_insufficient_balance_does_not_create_a_hold_or_receipt(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        assert_error("insufficient_credits", lambda: svc.reserve(conn, owner, reserve(1)))
        assert conn.execute(sa.select(sa.func.count()).select_from(t.wallets)).scalar_one() == 0
        grant(conn, svc, owner, staff)
        svc.reserve(conn, owner, reserve(70))
        assert_error("insufficient_credits", lambda: svc.reserve(conn, owner, reserve(31)))
        assert svc.overview(conn, owner).balance.available == 30
        assert svc.reconcile(conn, owner).consistent


@pytest.mark.parametrize("command_cls", [Grant, Reserve, Settle])
@pytest.mark.parametrize("value", [-1, 1.0, True, "1", 1_000_000_001])
def test_amount_is_strict_integer_and_bounded(command_cls, value):
    kwargs = dict(operation_id=uuid4(), amount=value)
    if command_cls == Grant:
        kwargs.update(case_id=uuid4(), reason="test_grant")
    else:
        kwargs["reservation_id"] = uuid4()
        if command_cls == Reserve:
            kwargs["request_id"] = uuid4()
    with pytest.raises(ValidationError):
        command_cls(**kwargs)


@pytest.mark.parametrize("kind", ["settle", "release"])
def test_foreign_reservation_and_missing_reservation_not_found(credit_env, kind):
    engine, svc, owner, other, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        grant(conn, svc, other, staff)
        hold = reserve()
        svc.reserve(conn, owner, hold)
        for reservation_id in [hold.reservation_id, uuid4()]:
            kwargs = dict(operation_id=uuid4(), reservation_id=reservation_id)
            cmd = Settle(**kwargs, amount=1) if kind == "settle" else Release(**kwargs)
            assert_error("not_found", lambda: getattr(svc, kind)(conn, other, cmd))
        assert svc.reconcile(conn, owner).consistent
        assert svc.overview(conn, other).balance.available == 100


def test_over_reservation_cost_does_not_spend_extra(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve(60)
        svc.reserve(conn, owner, hold)
        assert_error("reservation_exceeded", lambda: svc.settle(conn, owner,
            Settle(operation_id=uuid4(), reservation_id=hold.reservation_id, amount=61)))
        assert svc.overview(conn, owner).balance.reserved == 60
        assert svc.reconcile(conn, owner).consistent


@pytest.mark.parametrize("first,second", [
    ("settle", "settle"), ("settle", "release"),
    ("release", "settle"), ("release", "release")])
def test_closed_reservation_never_changes_with_new_operation(credit_env, first, second):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve()
        svc.reserve(conn, owner, hold)
        def command(kind):
            data = dict(operation_id=uuid4(), reservation_id=hold.reservation_id)
            return Settle(**data, amount=40) if kind == "settle" else Release(**data)
        getattr(svc, first)(conn, owner, command(first))
        assert_error("reservation_closed", lambda: getattr(svc, second)(conn, owner, command(second)))
        assert svc.reconcile(conn, owner).consistent


@pytest.mark.parametrize("state", ["generation_suspended", "security_locked", "deletion_pending", "deleted"])
def test_no_new_reserves_but_existing_obligations_can_be_closed(credit_env, state):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve()
        svc.reserve(conn, owner, hold)
        conn.execute(sa.update(auth_tables.accounts).where(
            auth_tables.accounts.c.id == owner).values(state=state))
        assert_error("account_restricted", lambda: svc.reserve(conn, owner, reserve(1)))
        svc.release(conn, owner, Release(operation_id=uuid4(), reservation_id=hold.reservation_id))
        assert svc.reconcile(conn, owner).consistent


def test_unverified_can_read_but_cannot_reserve(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        conn.execute(sa.update(auth_tables.identities).where(
            auth_tables.identities.c.account_id == owner).values(verified_at=None))
        assert svc.overview(conn, owner).balance.available == 100
        assert_error("verification_required", lambda: svc.reserve(conn, owner, reserve()))
