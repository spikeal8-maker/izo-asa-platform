"""Exercise the real Alembic revision loader/generator with temporary files only."""
import shutil
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def test_next_revision_can_be_generated_without_a_database(tmp_path):
    migrations = tmp_path / "migrations"
    shutil.copytree(ROOT / "apps/api/migrations", migrations)
    scripts = ScriptDirectory(str(migrations))
    before = set(migrations.rglob("*.py"))
    previous_head = scripts.get_current_head()
    revision = scripts.generate_revision("f0_test_next", "temporary acceptance revision")
    assert revision.revision == "f0_test_next"
    assert revision.down_revision == previous_head
    assert ScriptDirectory(str(migrations)).get_heads() == ["f0_test_next"]
    assert len(set(migrations.rglob("*.py")) - before) == 1


def test_readiness_uses_real_new_packaged_head(tmp_path, monkeypatch):
    from izo import health
    from izo.config import Settings
    from types import SimpleNamespace
    import sys

    migrations = tmp_path / "migrations"
    shutil.copytree(ROOT / "apps/api/migrations", migrations)
    scripts = ScriptDirectory(str(migrations))
    scripts.generate_revision("f0_test_next", "temporary acceptance revision")
    # Path resolution must not depend on the current working directory.
    monkeypatch.setattr(health, "__file__", str(tmp_path / "izo" / "health.py"))
    monkeypatch.chdir(tmp_path)
    health.expected_schema_revision.cache_clear()
    queries = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            queries.append(sql)
            return self

        def fetchall(self):
            return [("f0_test_next",)]

    def connect(**kwargs):
        assert kwargs["connect_timeout"] == 3
        assert "default_transaction_read_only=on" in kwargs["options"]
        assert "statement_timeout=2000" in kwargs["options"]
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    try:
        assert health.expected_schema_revision() == "f0_test_next"
        assert health.database_ready(Settings(pg_password="test-only"))
        assert queries == ["SELECT version_num FROM alembic_version"]
    finally:
        health.expected_schema_revision.cache_clear()


@pytest.mark.parametrize("heads", [[], ["branch-a", "branch-b"]])
def test_absent_or_diverged_packaged_heads_fail_closed(monkeypatch, heads):
    from izo import health
    from izo.config import Settings
    import sys
    from types import SimpleNamespace

    def unexpected_connection(**kwargs):
        pytest.fail("Ambiguous packaged schema must be rejected before connecting")

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=unexpected_connection))
    monkeypatch.setattr(ScriptDirectory, "get_heads", lambda self: heads)
    health.expected_schema_revision.cache_clear()
    try:
        with pytest.raises(ValueError, match="exactly one"):
            health.expected_schema_revision()
        assert not health.database_ready(Settings(pg_password="test-only"))
    finally:
        health.expected_schema_revision.cache_clear()
