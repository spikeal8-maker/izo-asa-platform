"""F0 review regressions: no external network, database, or real secrets."""
import json
import logging
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from izo.app import create_app
from izo.config import Settings
from izo import health


def fake_database(monkeypatch, rows):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            assert sql == "SELECT version_num FROM alembic_version"
            return self

        def fetchone(self):
            return rows[0] if rows else None

        def fetchall(self):
            return rows

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda **kw: Connection()))


def test_next_migration_does_not_require_editing_health(monkeypatch):
    # The future release contains 0002. The previous implementation ignores it.
    monkeypatch.setattr(health, "expected_schema_revision", lambda: "0002", raising=False)
    fake_database(monkeypatch, [("0002",)])
    assert health.database_ready(Settings(pg_password="test-only"))


def test_multiple_database_revisions_are_not_ready(monkeypatch):
    monkeypatch.setattr(health, "expected_schema_revision", lambda: "0001", raising=False)
    fake_database(monkeypatch, [("0001",), ("unexpected-branch",)])
    assert not health.database_ready(Settings(pg_password="test-only"))


@pytest.mark.parametrize("config", [
    {"s3_endpoint": "http://u:TESTSECRET@h"},
    {"pg_port": "TESTSECRET"},
])
def test_invalid_configuration_error_does_not_print_input(config):
    with pytest.raises(ValidationError) as exc:
        Settings(**config)
    assert "TESTSECRET" not in str(exc.value)
    assert "input_value" not in str(exc.value)


@pytest.mark.parametrize("endpoint", ["http://storage:not-a-port", "http://storage:65536", "http://storage:0"])
def test_malformed_storage_port_rejected_at_configuration(endpoint):
    with pytest.raises(ValidationError):
        Settings(s3_endpoint=endpoint)


def test_unhandled_error_has_safe_body_headers_and_event(caplog):
    app = create_app(Settings(), readiness=lambda: True)

    @app.get("/test-failure", include_in_schema=False)
    def fail():
        raise RuntimeError("TEST_PRIVATE_EXCEPTION")

    with caplog.at_level(logging.INFO, logger="izo.http"):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-failure?TEST_PRIVATE_QUERY=1", headers={"X-Request-ID": "untrusted"})
            assert client.get("/api/health/live").status_code == 200
    assert response.status_code == 500
    request_id = response.headers.get("X-Request-ID", "")
    assert len(request_id) == 32 and request_id != "untrusted"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json() == {"error": {"code": "internal_error", "request_id": request_id}}
    events = [json.loads(r.message) for r in caplog.records if r.name == "izo.http"]
    error_event = next(e for e in events if e["request_id"] == request_id)
    assert error_event["status"] == 500
    assert "TEST_PRIVATE" not in response.text + caplog.text


@pytest.mark.parametrize("status", [400, 403, 409, 429])
def test_handled_http_errors_keep_their_status(status):
    app = create_app(Settings(), readiness=lambda: True)

    @app.get("/test-handled", include_in_schema=False)
    def handled():
        raise HTTPException(status_code=status, detail="safe-public-code")

    with TestClient(app) as client:
        response = client.get("/test-handled")
    assert response.status_code == status
    assert response.json() == {"detail": "safe-public-code"}
    assert len(response.headers["x-request-id"]) == 32


@pytest.mark.parametrize("rows", [[], [("old",)], [("future",)], [("0001",), ("0001",)]])
def test_missing_mismatched_or_duplicate_schema_is_rejected(monkeypatch, rows):
    monkeypatch.setattr(health, "expected_schema_revision", lambda: "0001")
    fake_database(monkeypatch, rows)
    assert not health.database_ready(Settings(pg_password="test-only"))


@pytest.mark.parametrize("endpoint", ["http://storage:8333", "https://storage.example", "http://[::1]:8333"])
def test_valid_storage_endpoints_remain_supported(endpoint):
    assert Settings(s3_endpoint=endpoint).s3_endpoint == endpoint


def test_creating_app_does_not_probe_database_or_migrations(monkeypatch):
    def unexpected():
        pytest.fail("App construction must not inspect the live database")

    monkeypatch.setattr(health, "expected_schema_revision", unexpected)
    app = create_app(Settings())
    with TestClient(app) as client:
        assert client.get("/api/health/live").status_code == 200
        assert client.get("/api/v1/foundation").status_code == 200
