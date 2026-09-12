"""ADMIN-001 bounded scope, migration and shared HTTP safety checks."""
import ast
import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from izo.accounts import tables as a
from izo.admin import tables as t

ROOT=Path(__file__).resolve().parents[1]


def test_admin_never_writes_wallet_sql():
    for path in (ROOT/'apps/api/izo/admin').glob('*.py'):
        text=path.read_text(encoding="utf-8")
        assert 'sa.update(c.' not in text and 'sa.insert(c.' not in text
        assert 'credit_wallets' not in text and 'password_hash=' not in text
        assert 'create_all(' not in text
    service=(ROOT/'apps/api/izo/admin/service.py').read_text(encoding="utf-8")
    assert 'self.credits.grant(' in service
    assert 'access.staff_session(' in service


def test_accounts_facade_does_not_import_admin_or_ledger():
    tree=ast.parse((ROOT/'apps/api/izo/accounts/admin_access.py').read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):
            assert not any(x in (node.module or '') for x in ('admin.service','credits','providers'))


def test_admin_http_uses_existing_body_and_origin_guards():
    auth=(ROOT/'apps/api/izo/accounts/routes.py').read_text(encoding="utf-8")
    http=(ROOT/'apps/api/izo/accounts/http_security.py').read_text(encoding="utf-8")
    admin=(ROOT/'apps/api/izo/admin/routes.py').read_text(encoding="utf-8")
    assert 'from .http_security import AuthBodyLimit, same_origin' in auth
    assert 'from ..accounts.http_security import same_origin' in admin
    assert '"/api/v1/admin/"' in http and 'size > 8192' in http
    assert '"/api/v1/admin/"' in auth  # Redacted validation, including password input.


def test_real_browser_and_restart_checks_not_mock_only():
    ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding="utf-8")
    assert ci.index('admin_acceptance.py before') < ci.index('docker compose down\n')
    assert ci.index('admin_acceptance.py after') > ci.index('docker compose up --wait')
    assert 'node apps/web/acceptance/admin-live.mjs' in ci
    script=(ROOT/'apps/web/acceptance/admin-live.mjs').read_text(encoding="utf-8")
    assert 'route.fulfill' not in script
    assert 'IZO_ADMIN_ACCEPTANCE' in script
    assert ci.count('rm -f "$RUNNER_TEMP/izo-admin-state.json"')==2


def test_migration_matches_tables(tmp_path):
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    a.metadata.create_all(engine,tables=[table for table in a.metadata.sorted_tables if not table.name.startswith('admin_')])
    spec=importlib.util.spec_from_file_location('admin_migration',ROOT/'apps/api/migrations/versions/0006_admin.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.down_revision=='0005_entitlements'
    with engine.begin() as conn:
        module.op=Operations(MigrationContext.configure(conn))
        module.upgrade()
    inspector=sa.inspect(engine)
    for table in [t.events,t.policies]:
        assert {col['name'] for col in inspector.get_columns(table.name)}==set(table.c.keys())
        assert {x['name'] for x in inspector.get_check_constraints(table.name)}=={
            x.name for x in table.constraints if isinstance(x,sa.CheckConstraint)}
    with pytest.raises(RuntimeError,match='retained'):module.downgrade()
    engine.dispose()


def test_ui_does_not_fake_admin_or_store_password():
    for path in (ROOT/'apps/web/src/features/admin').glob('*.tsx'):
        text=path.read_text(encoding="utf-8")
        assert 'useDemo' not in text and 'sessionStorage' not in text and 'localStorage' not in text
        assert 'fetch(' not in text
    shell=(ROOT/'apps/web/src/shell/App.tsx').read_text(encoding="utf-8")
    assert 'Демо-пользователь 01' not in shell
    form=(ROOT/'apps/web/src/features/admin/GrantForm.tsx').read_text(encoding="utf-8")
    assert "body.current_password = ''" in form and "input.value = ''" in form
    assert 'previous.current.id' in form
