"""Forward migration preserves original media IDs and enforces source ownership."""
import importlib.util
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from izo.accounts import tables as a
from izo.jobs import tables as j
from izo.media import tables as m
from test_jobs import env, create

ROOT = Path(__file__).resolve().parents[1]


def migration(name):
    path = ROOT/'apps/api/migrations/versions'/name
    spec = importlib.util.spec_from_file_location(name.replace('.','_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_preserves_legacy_asset_and_checks_current_schema(tmp_path):
    engine = sa.create_engine('sqlite:///' + str(tmp_path/'migration.sqlite'))
    a.metadata.create_all(engine)
    owner, asset_id = uuid4(), uuid4()
    old = migration('0007_media.py')
    jobs = migration('0008_jobs.py')
    current = migration('0009_provider_calls.py')
    assert jobs.revision == '0008_jobs' and jobs.down_revision == '0007_media'
    assert current.revision == '0009_provider_calls' and current.down_revision == '0008_jobs'
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            old.upgrade()
            legacy = sa.MetaData()
            upload = sa.Table('media_uploads', legacy, autoload_with=conn)
            asset = sa.Table('media_assets', legacy, autoload_with=conn)
            conn.execute(sa.insert(a.accounts).values(id=owner, public_code='a'*16,
                display_name='Legacy fixture', state='active', created_at=100))
            key = f'assets/{owner.hex}/{asset_id.hex}/image.png'
            conn.execute(sa.insert(upload).values(id=asset_id.hex, account_id=owner.hex, operation_id=uuid4().hex,
                request_hash='a'*64, input_type='image/png', input_size=10, input_hash='b'*64,
                input_width=8, input_height=6, reserved_bytes=0, status='ready',
                created_at=100, expires_at=1000, object_key=key, stored_hash='b'*64,
                stored_size=10, width=8, height=6))
            conn.execute(sa.insert(asset).values(id=asset_id.hex, account_id=owner.hex, object_key=key,
                sha256='b'*64, byte_size=10, width=8, height=6, created_at=100))
            jobs.upgrade()
            current.upgrade()
        row = conn.execute(sa.select(m.assets)).mappings().one()
        assert row['id'] == row['upload_id'] == asset_id and row['output_id'] is None
        assert row['object_key'] == key and row['sha256'] == 'b'*64
        inspector = sa.inspect(conn)
        for table in (*m.TABLES, *j.TABLES):
            assert {c['name'] for c in inspector.get_columns(table.name)} == set(table.c.keys())
            assert {i['name'] for i in inspector.get_indexes(table.name)} == {i.name for i in table.indexes}
    with pytest.raises(RuntimeError):
        current.downgrade()
    with pytest.raises(RuntimeError):
        jobs.downgrade()
    engine.dispose()


def test_generated_asset_cannot_reference_another_owner_output(env):
    service, _, users, *_ = env
    job, _ = create(env)
    with service.auth.engine.connect() as conn:
        output_id = conn.execute(sa.select(j.jobs.c.output_id).where(j.jobs.c.id == job.id)).scalar_one()
    with pytest.raises(sa.exc.IntegrityError):
        with service.auth.engine.begin() as conn:
            conn.execute(sa.insert(m.assets).values(id=output_id, output_id=output_id,
                account_id=users[1].view.account.id, object_key='synthetic', sha256='a'*64,
                byte_size=10, width=64, height=64, created_at=2000))


def test_asset_requires_exactly_one_valid_source(env):
    service, _, users, *_ = env
    with pytest.raises(sa.exc.IntegrityError):
        with service.auth.engine.begin() as conn:
            conn.execute(sa.insert(m.assets).values(id=uuid4(), account_id=users[0].view.account.id,
                object_key='synthetic', sha256='a'*64, byte_size=10, width=64, height=64, created_at=2000))
