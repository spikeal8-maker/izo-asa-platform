"""CATALOG-001 migration shape on SQLite; PostgreSQL immutability is CI acceptance."""
import importlib.util
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.accounts import tables as accounts
from izo.catalog import tables as t

ROOT=Path(__file__).resolve().parents[1]


def migration():
    path=ROOT/'apps/api/migrations/versions/0010_catalog.py'
    spec=importlib.util.spec_from_file_location('catalog_migration',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def test_catalog_migration_matches_metadata_and_empty_downgrade(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'catalog.sqlite'))
    meta=sa.MetaData(); accounts.accounts.to_metadata(meta); meta.create_all(engine)
    m=migration(); assert m.revision=='0010_catalog' and m.down_revision=='0009_provider_execution'
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            inspector=sa.inspect(conn)
            for table in t.TABLES:
                assert {c['name'] for c in inspector.get_columns(table.name)}==set(table.c.keys())
            m.downgrade()
    assert sa.inspect(engine).get_table_names()==['accounts']
    engine.dispose()


def test_populated_catalog_downgrade_refuses_history_loss(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'catalog-populated.sqlite'))
    meta=sa.MetaData(); accounts.accounts.to_metadata(meta); meta.create_all(engine)
    m=migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
            conn.execute(sa.insert(t.capability_revisions).values(id=uuid4(),capability_id='x',revision=1,
                content_json='{}',content_hash='0'*64,created_at=1))
            with pytest.raises(RuntimeError,match='Populated'):
                m.downgrade()
            assert conn.execute(sa.select(sa.func.count()).select_from(t.capability_revisions)).scalar_one()==1
    engine.dispose()
