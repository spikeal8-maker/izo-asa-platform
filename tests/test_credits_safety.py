"""CREDIT-001 permission, audit, database and pagination safety invariants."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from izo.accounts import credit_access, tables as auth_tables
from izo.credits import tables as t
from izo.credits.schemas import Grant, MAX_BALANCE, Release, Settle
from credit_support import assert_error, credit_env, grant, reserve


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, 99, 1_000_000_001])
def test_grant_requires_a_trusted_finite_cap(credit_env, limit):
    engine, svc, owner, _, staff = credit_env
    g = Grant(operation_id=uuid4(), amount=100, case_id=uuid4(), reason="test_grant")
    with engine.begin() as conn:
        assert_error("grant_forbidden", lambda: svc.grant(conn, owner, staff, g, grant_limit=limit))
        assert svc.overview(conn, owner).balance.available == 0


@pytest.mark.parametrize("mode", ["missing", "expired", "suspended"])
def test_permission_is_checked_even_on_grant_replay(credit_env, mode):
    engine, svc, owner, _, staff = credit_env
    g = Grant(operation_id=uuid4(), amount=100, case_id=uuid4(), reason="test_grant")
    with engine.begin() as conn:
        grant(conn, svc, owner, staff, command=g)
        if mode == "missing":
            conn.execute(sa.delete(auth_tables.permissions).where(
                auth_tables.permissions.c.account_id == staff))
        elif mode == "expired":
            conn.execute(sa.update(auth_tables.permissions).where(
                auth_tables.permissions.c.account_id == staff).values(expires_at=2000))
        else:
            conn.execute(sa.update(auth_tables.accounts).where(
                auth_tables.accounts.c.id == staff).values(state="generation_suspended"))
        assert_error("grant_forbidden", lambda: grant(conn, svc, owner, staff, command=g))
        assert svc.overview(conn, owner).balance.sequence == 1


def test_audit_failure_rolls_back_wallet_reservation_and_entry_even_if_caught(credit_env, monkeypatch):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        def broken(*args):
            raise RuntimeError("synthetic audit failure")
        monkeypatch.setattr(credit_access, "record_event", broken)
        with pytest.raises(RuntimeError):
            svc.reserve(conn, owner, reserve())
        assert svc.overview(conn, owner).balance.sequence == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(t.reservations)).scalar_one() == 0
        assert svc.reconcile(conn, owner).consistent


def test_outer_job_transaction_can_rollback_credit_operations(credit_env):
    engine, svc, owner, _, staff = credit_env
    with pytest.raises(RuntimeError):
        with engine.begin() as conn:
            grant(conn, svc, owner, staff)
            svc.reserve(conn, owner, reserve())
            raise RuntimeError("simulated job creation failure")
    with engine.begin() as conn:
        assert svc.overview(conn, owner).balance.sequence == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(t.reservations)).scalar_one() == 0


def test_second_request_id_cannot_create_duplicate_reservations(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve(20)
        svc.reserve(conn, owner, hold)
        duplicate = hold.model_copy(update={"operation_id": uuid4(), "reservation_id": uuid4()})
        assert_error("credit_conflict", lambda: svc.reserve(conn, owner, duplicate))
        assert svc.overview(conn, owner).balance.reserved == 20
        assert svc.reconcile(conn, owner).consistent


def test_history_is_owner_scoped_keyset_paginated_and_excludes_actor_details(credit_env):
    engine, svc, owner, other, staff = credit_env
    with engine.begin() as conn:
        for _ in range(4):
            grant(conn, svc, owner, staff, amount=10)
        page = svc.overview(conn, owner, limit=2)
        assert [e.sequence for e in page.entries] == [4, 3]
        assert page.next_before == 3
        grant(conn, svc, owner, staff, amount=10)
        page2 = svc.overview(conn, owner, limit=2, before=page.next_before)
        assert [e.sequence for e in page2.entries] == [2, 1] and page2.next_before is None
        assert svc.overview(conn, other).entries == []
        assert not {"actor_id", "case_id", "request_hash"} & page.entries[0].model_dump().keys()


def test_projection_drift_is_detected_not_repaired(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        conn.execute(sa.update(t.wallets).where(t.wallets.c.account_id == owner).values(balance=99))
        assert not svc.reconcile(conn, owner).consistent
        assert svc.overview(conn, owner).balance.balance == 99


def test_database_constraints_reject_invalid_wallet_and_null_terminal_cost(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(sa.update(t.wallets).where(
                    t.wallets.c.account_id == owner).values(reserved=101))
        hold = reserve()
        svc.reserve(conn, owner, hold)
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(sa.update(t.reservations).where(
                    t.reservations.c.id == hold.reservation_id)
                    .values(state="settled", charged=None, closed_at=2000))


def test_credit_rows_prevent_accidental_cascade_account_deletion(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(sa.delete(auth_tables.accounts).where(
                    auth_tables.accounts.c.id == owner))


def test_zero_cost_success_releases_full_reservation_without_additional_credit(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve()
        svc.reserve(conn, owner, hold)
        svc.settle(conn, owner, Settle(
            operation_id=uuid4(), reservation_id=hold.reservation_id, amount=0))
        assert svc.overview(conn, owner).balance.available == 100
        assert svc.reconcile(conn, owner).consistent


@pytest.mark.parametrize("kind", ["grant", "reserve", "settle", "release"])
def test_every_mutation_rolls_back_its_receipt_and_projection_when_audit_fails(
        credit_env, monkeypatch, kind):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve(50)
        svc.reserve(conn, owner, hold)
        before = svc.overview(conn, owner).model_dump()
        def fail(*args):
            raise RuntimeError("audit unavailable")
        monkeypatch.setattr(credit_access, "record_event", fail)
        with pytest.raises(RuntimeError):
            if kind == "grant":
                grant(conn, svc, owner, staff, amount=10)
            elif kind == "reserve":
                svc.reserve(conn, owner, reserve(20))
            elif kind == "settle":
                svc.settle(conn, owner, Settle(
                    operation_id=uuid4(), reservation_id=hold.reservation_id, amount=20))
            else:
                svc.release(conn, owner, Release(
                    operation_id=uuid4(), reservation_id=hold.reservation_id))
        assert svc.overview(conn, owner).model_dump() == before
        assert svc.reconcile(conn, owner).consistent


def test_malformed_constructed_amount_is_revalidated(credit_env):
    engine, svc, owner, _, staff = credit_env
    bad = Grant.model_construct(operation_id=uuid4(), case_id=uuid4(),
                                amount=True, reason="test_grant")
    with engine.begin() as conn:
        with pytest.raises(ValidationError):
            svc.grant(conn, owner, staff, bad, grant_limit=100)
        assert svc.overview(conn, owner).entries == []


def test_operation_identifier_can_be_used_by_different_accounts_without_leaking_receipts(credit_env):
    engine, svc, owner, other, staff = credit_env
    op = uuid4()
    with engine.begin() as conn:
        a = grant(conn, svc, owner, staff, command=Grant(
            operation_id=op, case_id=uuid4(), amount=10, reason="test_grant"))
        b = grant(conn, svc, other, staff, command=Grant(
            operation_id=op, case_id=uuid4(), amount=20, reason="test_grant"))
        assert a.entry_id != b.entry_id and a.balance_after == 10 and b.balance_after == 20


def test_wallet_safety_limit_rejects_without_a_second_grant(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        conn.execute(sa.update(t.wallets).where(
            t.wallets.c.account_id == owner).values(balance=MAX_BALANCE))
        assert_error("credit_bounds", lambda: grant(conn, svc, owner, staff, amount=1))
        assert svc.overview(conn, owner).balance.sequence == 1


@pytest.mark.parametrize("limit,before", [
    (True, None), (0, None), (101, None), (1, 0), (1, -1), (1, True), (1, 1.5)])
def test_service_pagination_is_bounded_even_without_http(credit_env, limit, before):
    engine, svc, owner, _, _ = credit_env
    with engine.begin() as conn:
        assert_error("invalid_pagination", lambda: svc.overview(
            conn, owner, limit=limit, before=before))


def test_service_rejects_commands_outside_explicit_transaction(credit_env):
    engine, svc, owner, _, _ = credit_env
    with engine.connect() as conn:
        with pytest.raises(RuntimeError, match="explicit caller transaction"):
            svc.reserve(conn, owner, reserve())
