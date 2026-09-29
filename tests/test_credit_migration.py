"""Migration structure and transaction behavior; PostgreSQL DDL rendering is not execution."""
import importlib.util
import io
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.accounts import tables as a
from izo.credits import tables as c
from izo.credits.schemas import Grant
from izo.credits.service import CreditService
from test_credits import credit_env, grant

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'apps/api/migrations/versions/0004_credits.py'
spec = importlib.util.spec_from_file_location('credit_migration_0004', PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_migration_has_correct_parent_and_no_runtime_schema_import():
    assert migration.revision == '0004_credits' and migration.down_revision == '0003'
    text=PATH.read_text()
    assert 'izo.credits' not in text and 'create_all' not in text


def test_real_sqlite_upgrade_matches_static_metadata_and_empty_downgrade():
    engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        for table in a.metadata.sorted_tables:
            if not table.name.startswith('credit_'):
                table.create(conn)
        ctx=MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        assert compare_metadata(ctx, a.metadata) == []
        with Operations.context(ctx):
            migration.downgrade()
        assert not any(name.startswith('credit_') for name in sa.inspect(conn).get_table_names())
    engine.dispose()


def test_populated_downgrade_is_refused(credit_env):
    engine, svc, owner, other, staff = credit_env
    with engine.begin() as conn:
        grant(conn, svc, owner, staff)
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match='populated credit ledger'):
                migration.downgrade()
        assert svc.overview(conn, owner).balance.available == 100


def test_postgres_ddl_contains_fk_bounds_and_immutability_triggers():
    output = io.StringIO()
    ctx=MigrationContext.configure(dialect_name='postgresql', opts={'as_sql':True, 'output_buffer':output})
    with Operations.context(ctx):
        migration.upgrade()
    text=output.getvalue()
    assert 'REFERENCES accounts (id)' in text
    assert 'credit_wallet_bounds' in text and 'credit_operation_once' in text
    assert 'BEFORE UPDATE OR DELETE ON credit_ledger' in text
    assert 'BEFORE TRUNCATE ON credit_ledger' in text
    assert '0002' not in text
