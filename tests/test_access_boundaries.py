"""ACCESS-001 scope, migration and authorization-boundary guards."""
import ast
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from izo.accounts import tables as accounts
from izo.access import tables as access_tables
from izo.access.permissions import GLOBAL_DELEGABLE

ROOT = Path(__file__).resolve().parents[1]
ACCESS_NAMES = {table.name for table in access_tables.TABLES}


def test_access_registry_has_no_wildcards_or_role_levels():
    assert GLOBAL_DELEGABLE
    assert all('*' not in item and item.count('.') == 1 for item in GLOBAL_DELEGABLE)
    assert 'access.manage' in GLOBAL_DELEGABLE and 'plans.write' in GLOBAL_DELEGABLE
    source=(ROOT/'apps/api/izo/access/permissions.py').read_text(encoding='utf-8')
    assert 'role level' not in source.lower() and 'root.' not in source


def test_access_service_uses_accounts_materialization_and_fresh_auth():
    source=(ROOT/'apps/api/izo/access/service.py').read_text(encoding='utf-8')
    assert 'accounts.permissions' in source
    assert 'verify_password(' in source and 'access.staff_session(' in source
    assert 'self_delegation_forbidden' in source and 'last_access_owner' in source
    assert 'raw key' not in source.lower()


def test_access_http_is_attached_and_uses_shared_guards():
    app=(ROOT/'apps/api/izo/app.py').read_text(encoding='utf-8')
    routes=(ROOT/'apps/api/izo/access/routes.py').read_text(encoding='utf-8')
    security=(ROOT/'apps/api/izo/accounts/http_security.py').read_text(encoding='utf-8')
    assert 'attach_access(app, accounts_service)' in app
    assert 'same_origin(request, auth)' in routes
    assert 'no_query(request)' in routes and 'if request.query_params:' in routes
    assert '"/api/v1/admin/"' in security


def test_access_migration_matches_tables(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'access.sqlite'))
    base=[table for table in accounts.metadata.sorted_tables if table.name not in ACCESS_NAMES]
    # Only Accounts is required for ACCESS FKs; avoid constructing unrelated domain tables.
    accounts.metadata.create_all(engine, tables=[table for table in base if table.name in {'accounts'}])
    path=ROOT/'apps/api/migrations/versions/0010_access.py'
    spec=importlib.util.spec_from_file_location('access_migration',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.revision=='0010_access' and module.down_revision=='0009_provider_calls'
    with engine.begin() as conn:
        module.op=Operations(MigrationContext.configure(conn))
        module.upgrade()
        inspector=sa.inspect(conn)
        for table in access_tables.TABLES:
            assert {c['name'] for c in inspector.get_columns(table.name)}==set(table.c.keys())
            assert {i['name'] for i in inspector.get_indexes(table.name)}=={i.name for i in table.indexes}
            assert {c['name'] for c in inspector.get_check_constraints(table.name)}=={
                c.name for c in table.constraints if isinstance(c,sa.CheckConstraint)}
        row=conn.execute(sa.text('SELECT id,version FROM staff_access_state')).one()
        assert row==(1,0)
    with pytest.raises(RuntimeError,match='retained'): module.downgrade()
    engine.dispose()
