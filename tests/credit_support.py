"""Shared CREDIT-001 unit fixtures and helpers."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.accounts import tables as auth_tables
from izo.credits.schemas import CreditError, Grant, Reserve
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
            conn.execute(sa.insert(auth_tables.accounts).values(
                id=account_id, public_code=account_id.hex[:16],
                display_name="Synthetic credits fixture", state="active", created_at=1000))
            conn.execute(sa.insert(auth_tables.identities).values(
                id=uuid4(), account_id=account_id, provider="email",
                subject=account_id.hex + "@example.invalid", verified_at=1000))
        conn.execute(sa.insert(auth_tables.permissions).values(
            account_id=staff, permission="credits.grant"))
    yield engine, CreditService(clock=lambda: 2000), owner, other, staff
    engine.dispose()


def grant(conn, service, owner, staff, amount=100, command=None):
    command = command or Grant(operation_id=uuid4(), amount=amount,
                               case_id=uuid4(), reason="test_grant")
    return service.grant(conn, owner, staff, command, grant_limit=1000)


def reserve(amount=70, **kwargs):
    return Reserve(operation_id=uuid4(), reservation_id=uuid4(),
                   request_id=uuid4(), amount=amount, **kwargs)


def assert_error(code, action):
    with pytest.raises(CreditError) as exc:
        action()
    assert exc.value.code == code
