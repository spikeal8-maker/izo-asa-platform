"""Shared Accounts fixtures/helpers; no test cases live here."""
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from izo.app import create_app
from izo.config import Settings
from izo.accounts import tables as t
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings

ORIGIN = "http://localhost:8080"
HEADERS = {"origin": ORIGIN, "x-izo-request": "web"}
PASSWORD = "test-only strong password 2026"


@pytest.fixture
def context():
    engine = sa.create_engine("sqlite+pysqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    t.metadata.create_all(engine)
    clock = [1800000000]
    policy = AuthSettings(registration="open", rate_secret="test-rate-key-" * 4)
    service = AuthService(engine, policy, clock=lambda: clock[0])
    app = create_app(Settings(), readiness=lambda: True)
    app.state.accounts_service = service
    with TestClient(app, base_url=ORIGIN) as client:
        yield service, client, clock
    engine.dispose()


def registration(_service, email="alice@example.invalid", **extra):
    return {"email": email, "password": PASSWORD, "display_name": "Тестовый пользователь", **extra}


def signup(service, client, email="alice@example.invalid"):
    result = client.post("/api/v1/auth/register", json=registration(service, email), headers=HEADERS)
    assert result.status_code == 201, result.text
    return result
