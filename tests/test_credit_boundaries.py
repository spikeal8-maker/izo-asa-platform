"""CREDIT-001 executable scope boundaries; these do not replace branch protection."""
import ast
from pathlib import Path
from fastapi import FastAPI

from izo.credits.routes import attach_credits

ROOT = Path(__file__).resolve().parents[1]


def test_credits_never_commits_callers_transaction_or_calls_an_ai_provider():
    for path in (ROOT/'apps/api/izo/credits').glob('*.py'):
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 400 and len(text.encode()) <= 20000
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {'commit', 'create_all'}, path
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
                assert all(name.split('.')[0] not in {'requests','httpx','boto3','openai','subprocess'} for name in names)


def test_all_accounts_reads_in_credits_go_through_the_owned_access_facade():
    for path in (ROOT/'apps/api/izo/credits').glob('*.py'):
        source = path.read_text(encoding="utf-8")
        assert 'password_credentials' not in source
        assert 'accounts.repository' not in source
        assert 'accounts.tables' not in source
        assert 'auth_identities' not in source


def test_read_contract_has_no_mutation_or_requested_owner_field():
    app = FastAPI()
    def unresolved(request):
        raise AssertionError('Schema export must not resolve database or sessions')
    attach_credits(app, unresolved)
    schema = app.openapi()
    assert set(schema['paths']) == {'/api/v1/credits'}
    assert set(schema['paths']['/api/v1/credits']) == {'get'}
    operation = schema['paths']['/api/v1/credits']['get']
    assert {p['name'] for p in operation['parameters']} == {'limit', 'before'}
    assert 'requestBody' not in operation
    for response in ['Entry', 'Overview']:
        assert not {'actor_id', 'case_id', 'request_hash'} & schema['components']['schemas'][response]['properties'].keys()


def test_root_wires_existing_auth_resolver_without_another_login_system():
    root = (ROOT/'apps/api/izo/app.py').read_text(encoding="utf-8")
    accounts = (ROOT/'apps/api/izo/accounts/routes.py').read_text(encoding="utf-8")
    assert 'accounts_service = attach_accounts(app, config)' in root
    assert 'attach_credits(app, accounts_service)' in root
    assert accounts.rstrip().endswith('return service')


def test_pg_acceptance_is_isolated_and_does_not_erase_the_ledger():
    source=(ROOT/'tools/credit_acceptance.py').read_text(encoding="utf-8")
    assert 'IZO_CREDIT_ACCEPTANCE' in source and 'config.environment != "test"' in source
    assert 'DISABLE TRIGGER' not in source and 'DROP SCHEMA' not in source
    assert 'CREDIT_BEFORE_OK' in source and 'CREDIT_AFTER_OK' in source
    ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding="utf-8")
    assert 'credit_acceptance.py before > "$RUNNER_TEMP/izo-credit-state.json"' in ci
    assert 'credit_acceptance.py after < "$RUNNER_TEMP/izo-credit-state.json"' in ci
    assert ci.count('rm -f "$RUNNER_TEMP/izo-credit-state.json"') == 2
    assert 'contents: read' in ci and 'self-hosted' not in ci and 'secrets.' not in ci
