"""CATALOG UI static guards; behavior/viewport coverage lives in Playwright."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ADMIN=ROOT/'apps/web/src/features/admin'


def text(name): return (ADMIN/name).read_text(encoding='utf-8')


def test_catalog_ui_never_contains_provider_secret_or_live_activation_controls():
    joined='\n'.join(text(name) for name in (
        'CatalogPage.tsx','CatalogModelPage.tsx','CatalogConnectionPage.tsx','CatalogCredentialPage.tsx'))
    assert 'api_key' not in joined and 'Bearer ' not in joined
    assert 'localStorage' not in joined and 'sessionStorage' not in joined
    assert "runtime_state:'active'" not in joined and 'runtime_state: "active"' not in joined
    assert 'fetch(' not in joined and 'openrouter.ai/api/v1/images' in joined  # display-only fixed endpoint


def test_catalog_navigation_does_not_require_user_admin_permission():
    page=text('AdminPage.tsx')
    assert "permissions.includes('catalog.read') ? '/admin/models'" in page
    assert "permissions.includes('connections.read') ? '/admin/providers'" in page
    assert 'isCatalogPath(path) ? <CatalogPage' in page


def test_credential_screen_uses_reference_and_fingerprint_not_raw_value():
    page=text('CatalogCredentialPage.tsx')
    assert 'secret_ref:secretRef' in page and 'reference_fingerprint' in page
    assert 'Текущий пароль для привязки' in page and "setBindPassword('')" in page
    assert 'Значение API-ключа не вводится' in page
