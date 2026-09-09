"""Keep worker scope, immutable migrations and existing CI gates explicit."""
import ast
from pathlib import Path
import pytest
from izo.jobs.catalog import JobSettings
from izo.jobs.worker import main

ROOT = Path(__file__).resolve().parents[1]


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv('IZO_JOBS_ENABLED', raising=False)
    assert JobSettings().enabled is False


def test_worker_requires_an_explicit_test_environment(monkeypatch):
    monkeypatch.setattr('sys.argv',['worker','--once'])
    monkeypatch.setenv('IZO_ENVIRONMENT','production')
    with pytest.raises(SystemExit,match='development/test'):
        main()


def test_public_contract_has_no_worker_write_routes():
    source = (ROOT/'apps/api/izo/jobs/routes.py').read_text()
    for forbidden in ('"/claim"','"/finish"','"/heartbeat"','"/settle"'):
        assert forbidden not in source
    assert 'same_origin(' in source
    assert 'RequestValidationError' in source


def test_no_alternative_credit_or_media_sql_in_job_service():
    for name in ('service.py','execution.py','recovery.py'):
        source = (ROOT/'apps/api/izo/jobs'/name).read_text()
        assert 'credit_ledger' not in source and 'media_assets' not in source
        assert 'httpx' not in source and 'requests.' not in source
    source = (ROOT/'apps/api/izo/media/outputs.py').read_text()
    assert 'CreditService' not in source


def test_worker_is_opt_in_and_not_started_by_api_import():
    app = (ROOT/'apps/api/izo/app.py').read_text()
    assert 'jobs.worker' not in app and 'Thread(' not in app
    compose = (ROOT/'compose.yaml').read_text()
    assert 'profiles: [jobs]' in compose and 'IZO_JOBS_ENABLED:-false' in compose
    assert "command: [python, '-m', izo.jobs.worker]" in compose
    assert 'no-new-privileges:true' in compose


def test_ci_keeps_old_tests_and_tests_jobs_on_both_sides_of_restart():
    workflow = (ROOT/'.github/workflows/ci.yml').read_text()
    assert workflow.index('tools/jobs_acceptance.py before') < workflow.index('docker compose down\n')
    assert workflow.index('tools/jobs_acceptance.py after') > workflow.index('docker compose up --wait')
    assert workflow.count('rm -f "$RUNNER_TEMP/izo-jobs-state.json"') == 2
    assert 'IZO_JOBS_ACCEPTANCE=isolated' in workflow and 'umask 077' in workflow
    for name in ('auth','email','credit','entitlement','admin','media'):
        assert f'tools/{name}_acceptance.py before' in workflow
        assert f'tools/{name}_acceptance.py after' in workflow
    for name in ('ci.yml','dependency-audit.yml'):
        source = (ROOT/'.github/workflows'/name).read_text()
        assert '  pull_request: {}' in source
        assert 'contents: read' in source and 'persist-credentials: false' in source
        assert 'pull_request_target' not in source and 'continue-on-error' not in source


def test_job_migration_has_no_application_imports():
    path = ROOT/'apps/api/migrations/versions/0008_jobs.py'
    tree = ast.parse(path.read_text())
    assert not any(isinstance(node,ast.ImportFrom) and 'izo' in (node.module or '') for node in ast.walk(tree))
    assert 'down_revision = "0007_media"' in path.read_text()


def test_acceptance_has_separate_process_and_never_changes_global_plan():
    script = (ROOT/'tools/jobs_acceptance.py').read_text()
    assert "'-m', 'izo.jobs.worker'" in script
    assert 'set_default(' not in script
    assert 'TRUNCATE' not in script and 'DISABLE TRIGGER' not in script
