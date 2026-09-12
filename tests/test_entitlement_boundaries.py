"""Enforce the small entitlement boundary, not a second provider/billing system."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_pure_policy_does_not_import_infrastructure():
    allowed={'uuid','typing','pydantic','schemas'}
    for filename in ['schemas.py','policy.py']:
        tree=ast.parse((ROOT/'apps/api/izo/entitlements'/filename).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                assert all(n.name.split('.')[0] in allowed for n in node.names)
            if isinstance(node,ast.ImportFrom):
                assert node.module.split('.')[0] in allowed


def test_no_credit_mutations_or_direct_account_tables():
    service=(ROOT/'apps/api/izo/entitlements/service.py').read_text(encoding="utf-8")
    for forbidden in ['.grant(','.reserve(','.settle(','.release(', 'account_tables','password_hash','httpx','requests']:
        assert forbidden not in service
    assert 'entitlement_access' in service
    assert '.overview(' in service


def test_route_uses_same_session_transaction_and_exposes_get_only():
    source=(ROOT/'apps/api/izo/entitlements/routes.py').read_text(encoding="utf-8")
    assert 'auth._session(conn,' in source
    for forbidden in ['@router.post','@router.put','@router.delete','assess_image(', 'api_key']:
        assert forbidden not in source


def test_migration_is_independent_and_sensitive_files_scoped():
    import json
    source=(ROOT/'apps/api/migrations/versions/0005_entitlements.py').read_text(encoding="utf-8")
    assert 'from izo' not in source and 'from ..' not in source
    assert 'immutable' in source and 'TRUNCATE' in source
    scope=json.loads((ROOT/'tools/scopes/entitlement-001.json').read_text(encoding="utf-8"))
    assert scope['max_files']<=24
