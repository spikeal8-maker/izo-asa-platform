"""SETTINGS-002 ownership and architecture boundaries."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT/path).read_text(encoding='utf-8')


def test_settings_reuses_entitlements_and_adds_no_settings_migration():
    service=read('apps/api/izo/settings/service.py')
    tables=read('apps/api/izo/entitlements/tables.py')
    assert 'ent_tables.revisions' in service and 'ent_tables.defaults' in service
    assert 'ent_tables.changes' in service
    assert 'settings_' not in tables
    assert not list((ROOT/'apps/api/migrations/versions').glob('*settings*'))


def test_settings_code_has_no_provider_secret_or_generic_config_store():
    text='\n'.join(read('apps/api/izo/settings/'+name)
        for name in ('schemas.py','service.py','routes.py'))
    for forbidden in ('openrouter','fal.ai','credential','secretstr','os.environ','BaseSettings'):
        assert forbidden.lower() not in text.lower()
    assert 'dict[str, Any]' not in text and 'dict[str,Any]' not in text

def test_permissions_and_http_surface_are_narrow():
    service=read('apps/api/izo/settings/service.py')
    routes=read('apps/api/izo/settings/routes.py')
    assert '{"plans.read"}' in service and '{"plans.write"}' in service
    assert '/api/v1/admin/settings' in routes
    assert 'query_params(request, set())' in routes
    assert 'same_origin(request, auth)' in routes
    assert 'plans.write' not in routes


def test_composition_root_attaches_settings_once_after_access():
    app=read('apps/api/izo/app.py')
    assert app.count('from .settings.routes import attach_settings') == 1
    assert app.count('attach_settings(app, accounts_service)') == 1
    assert app.index('attach_access(app, accounts_service)') < app.index('attach_settings(app, accounts_service)')


def test_settings_local_map_is_small_and_current():
    text=read('apps/api/izo/settings/README.md')
    assert len(text.encode('utf-8')) < 5000
    assert 'SETTINGS-002' in text and 'ACCESS-001' in text
    assert 'CATALOG-002' in text
    assert 'OpenRouter' not in text

def test_settings_acceptance_does_not_pollute_following_access_gate():
    text=read('tools/settings_acceptance.py')
    assert 'def cleanup_bootstrap_owner' in text
    assert 'access_tables.grants' in text and 'access_tables.ceilings' in text
    assert 'account_tables.permissions' in text and 'GLOBAL_DELEGABLE' in text
    assert 'cleanup_bootstrap_owner(auth,UUID(owner["id"]))' in text
