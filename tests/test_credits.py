"""CREDIT-001 unit invariants. SQLite tests do not claim PostgreSQL locking."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from izo.accounts import tables as auth_tables, credit_access
from izo.credits import tables as t
from izo.credits.schemas import CreditError, Grant, Reserve, Settle, Release, MAX_BALANCE
from izo.credits.service import CreditService


@pytest.fixture
def credit_env(tmp_path):
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "credits.sqlite"),
                              connect_args={"check_same_thread": False})
    @sa.event.listens_for(engine, "connect")
    def configure(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
    @sa.event.listens_for(engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")
    auth_tables.metadata.create_all(engine)
    owner, other, staff = uuid4(), uuid4(), uuid4()
    with engine.begin() as conn:
        for account_id in [owner, other, staff]:
            conn.execute(sa.insert(auth_tables.accounts).values(id=account_id, public_code=account_id.hex[:16],
                display_name="Synthetic credits fixture", state="active", created_at=1000))
            conn.execute(sa.insert(auth_tables.identities).values(id=uuid4(), account_id=account_id,
                provider="email", subject=account_id.hex + "@example.invalid", verified_at=1000))
        conn.execute(sa.insert(auth_tables.permissions).values(account_id=staff, permission="credits.grant"))
    yield engine, CreditService(clock=lambda: 2000), owner, other, staff
    engine.dispose()


def grant(conn, service, owner, staff, amount=100, command=None):
    command = command or Grant(operation_id=uuid4(), amount=amount, case_id=uuid4(), reason="test_grant")
    return service.grant(conn, owner, staff, command, grant_limit=1000)


def reserve(amount=70, **kwargs):
    return Reserve(operation_id=uuid4(), reservation_id=uuid4(), request_id=uuid4(), amount=amount, **kwargs)


def assert_error(code, action):
    with pytest.raises(CreditError) as exc:
        action()
    assert exc.value.code == code


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
        final = svc.settle(conn, owner, Settle(operation_id=uuid4(), reservation_id=hold.reservation_id, amount=50))
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
                          if kind == "settle" else Release(operation_id=uuid4(), reservation_id=hold.reservation_id))
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
            call = lambda: grant(conn, svc, owner, staff, command=g.model_copy(update={"amount": 101}))
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


@pytest.mark.parametrize("first,second", [("settle","settle"),("settle","release"),("release","settle"),("release","release")])
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


@pytest.mark.parametrize("state", ["generation_suspended","security_locked","deletion_pending","deleted"])
def test_no_new_reserves_but_existing_obligations_can_be_closed(credit_env, state):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold = reserve()
        svc.reserve(conn, owner, hold)
        conn.execute(sa.update(auth_tables.accounts).where(auth_tables.accounts.c.id == owner).values(state=state))
        assert_error("account_restricted", lambda: svc.reserve(conn, owner, reserve(1)))
        svc.release(conn, owner, Release(operation_id=uuid4(), reservation_id=hold.reservation_id))
        assert svc.reconcile(conn, owner).consistent


def test_unverified_can_read_but_cannot_reserve(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        conn.execute(sa.update(auth_tables.identities).where(auth_tables.identities.c.account_id == owner).values(verified_at=None))
        assert svc.overview(conn, owner).balance.available == 100
        assert_error("verification_required", lambda: svc.reserve(conn, owner, reserve()))


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
            conn.execute(sa.delete(auth_tables.permissions).where(auth_tables.permissions.c.account_id == staff))
        elif mode == "expired":
            conn.execute(sa.update(auth_tables.permissions).where(auth_tables.permissions.c.account_id == staff).values(expires_at=2000))
        else:
            conn.execute(sa.update(auth_tables.accounts).where(auth_tables.accounts.c.id == staff).values(state="generation_suspended"))
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
        duplicate = hold.model_copy(update={"operation_id":uuid4(), "reservation_id":uuid4()})
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
        assert not {"actor_id","case_id","request_hash"} & page.entries[0].model_dump().keys()


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
                conn.execute(sa.update(t.wallets).where(t.wallets.c.account_id == owner).values(reserved=101))
        hold = reserve()
        svc.reserve(conn, owner, hold)
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(sa.update(t.reservations).where(t.reservations.c.id==hold.reservation_id)
                    .values(state="settled", charged=None, closed_at=2000))


def test_credit_rows_prevent_accidental_cascade_account_deletion(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(sa.delete(auth_tables.accounts).where(auth_tables.accounts.c.id == owner))


def test_zero_cost_success_releases_full_reservation_without_additional_credit(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        hold=reserve()
        svc.reserve(conn, owner, hold)
        svc.settle(conn, owner, Settle(operation_id=uuid4(), reservation_id=hold.reservation_id, amount=0))
        assert svc.overview(conn, owner).balance.available == 100
        assert svc.reconcile(conn, owner).consistent

@pytest.mark.parametrize("kind", ["grant", "reserve", "settle", "release"])
def test_every_mutation_rolls_back_its_receipt_and_projection_when_audit_fails(credit_env, monkeypatch, kind):
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
                svc.settle(conn, owner, Settle(operation_id=uuid4(), reservation_id=hold.reservation_id, amount=20))
            else:
                svc.release(conn, owner, Release(operation_id=uuid4(), reservation_id=hold.reservation_id))
        assert svc.overview(conn, owner).model_dump() == before
        assert svc.reconcile(conn, owner).consistent


def test_malformed_constructed_amount_is_revalidated(credit_env):
    engine, svc, owner, _, staff = credit_env
    bad = Grant.model_construct(operation_id=uuid4(), case_id=uuid4(), amount=True, reason="test_grant")
    with engine.begin() as conn:
        with pytest.raises(ValidationError):
            svc.grant(conn, owner, staff, bad, grant_limit=100)
        assert svc.overview(conn, owner).entries == []


def test_operation_identifier_can_be_used_by_different_accounts_without_leaking_receipts(credit_env):
    engine, svc, owner, other, staff = credit_env
    op = uuid4()
    with engine.begin() as conn:
        a=grant(conn, svc, owner, staff, command=Grant(operation_id=op, case_id=uuid4(), amount=10, reason="test_grant"))
        b=grant(conn, svc, other, staff, command=Grant(operation_id=op, case_id=uuid4(), amount=20, reason="test_grant"))
        assert a.entry_id != b.entry_id and a.balance_after == 10 and b.balance_after == 20


def test_wallet_safety_limit_rejects_without_a_second_grant(credit_env):
    engine, svc, owner, _, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        # Synthetic boundary fixture, not a supported balance-edit operation.
        conn.execute(sa.update(t.wallets).where(t.wallets.c.account_id == owner).values(balance=MAX_BALANCE))
        assert_error("credit_bounds", lambda: grant(conn, svc, owner, staff, amount=1))
        assert svc.overview(conn, owner).balance.sequence == 1


@pytest.mark.parametrize("limit,before", [(True,None),(0,None),(101,None),(1,0),(1,-1),(1,True),(1,1.5)])
def test_service_pagination_is_bounded_even_without_http(credit_env, limit, before):
    engine, svc, owner, _, _ = credit_env
    with engine.begin() as conn:
        assert_error("invalid_pagination", lambda: svc.overview(conn, owner, limit=limit, before=before))


def test_service_rejects_commands_outside_explicit_transaction(credit_env):
    engine, svc, owner, _, _ = credit_env
    with engine.connect() as conn:
        with pytest.raises(RuntimeError, match="explicit caller transaction"):
            svc.reserve(conn, owner, reserve())
