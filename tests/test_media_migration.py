"""Migration snapshot and composite ownership FK; PostgreSQL is verified in CI."""
import importlib.util
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from izo.accounts import tables as a
from izo.media import tables as t

ROOT=Path(__file__).resolve().parents[1]


def test_migration_is_additive_and_matches_metadata(tmp_path):
    path=ROOT/'apps/api/migrations/versions/0007_media.py'
    spec=importlib.util.spec_from_file_location('media_migration_snapshot',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision=='0007_media' and module.down_revision=='0006_admin'
    assert 'izo.media' not in path.read_text()
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    a.metadata.create_all(engine)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            path8=ROOT/'apps/api/migrations/versions/0008_jobs.py'
            spec8=importlib.util.spec_from_file_location('jobs_media_extension_snapshot',path8)
            module8=importlib.util.module_from_spec(spec8)
            spec8.loader.exec_module(module8)
            module8.upgrade()
        inspector=sa.inspect(conn)
        for table in t.TABLES:
            assert {x['name'] for x in inspector.get_columns(table.name)}==set(table.c.keys())
            assert {x['name'] for x in inspector.get_indexes(table.name)}=={x.name for x in table.indexes}
    with pytest.raises(RuntimeError): module.downgrade()
    engine.dispose()


def test_media_contract_uses_composite_upload_owner_reference():
    assert any([x.target_fullname for x in fk.elements]==['media_uploads.id','media_uploads.account_id']
               for fk in t.assets.foreign_key_constraints)
