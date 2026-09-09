"""Exercise migration SQL on SQLite; PG guards are tested by real CI acceptance."""
import importlib.util
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from izo.accounts import tables as a
from izo.entitlements import tables as t

ROOT=Path(__file__).resolve().parents[1]


def migration():
    spec=importlib.util.spec_from_file_location('entitlement_migration',ROOT/'apps/api/migrations/versions/0005_entitlements.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_matches_metadata_and_empty_downgrade(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    meta=sa.MetaData()
    a.accounts.to_metadata(meta)
    meta.create_all(engine)
    m=migration()
    assert m.down_revision=='0004_credits'
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            inspector=sa.inspect(conn)
            for table in [t.revisions,t.defaults,t.assignments,t.changes]:
                assert {c['name'] for c in inspector.get_columns(table.name)}==set(table.c.keys())
            assert conn.execute(sa.select(t.defaults.c.version)).scalar_one()==0
            assert conn.execute(sa.select(t.defaults.c.revision_id)).scalar_one() is None
            m.downgrade()
    assert sa.inspect(engine).get_table_names()==['accounts']
    engine.dispose()


def test_populated_downgrade_is_not_data_loss(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'populated.sqlite'))
    meta=sa.MetaData(); a.accounts.to_metadata(meta);meta.create_all(engine)
    m=migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            conn.execute(sa.insert(t.revisions).values(id=uuid4(),plan_code='basic',revision=1,
                policy_json='{}',policy_hash='0'*64,created_at=1))
            with pytest.raises(RuntimeError,match='Populated'):
                m.downgrade()
            assert conn.execute(sa.select(sa.func.count()).select_from(t.revisions)).scalar_one()==1
    engine.dispose()
