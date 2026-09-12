"""Documentation/navigation regression tests for low-token maintenance."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_context(task: str):
    return subprocess.run(
        [sys.executable, str(ROOT/'tools/context.py'), '--task', task, '--json'],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )


def test_documentation_validator_passes():
    result = subprocess.run([sys.executable, str(ROOT/'tools/check_docs.py')], cwd=ROOT,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DOCS CHECK OK' in result.stdout


def test_routing_corpus_prefers_correct_or_safe_failure():
    cases = json.loads((ROOT/'tests/context_cases.json').read_text(encoding='utf-8'))
    for case in cases:
        result = run_context(case['task'])
        if case['status'] == 'resolved':
            assert result.returncode == 0, (case, result.stderr)
            data = json.loads(result.stdout)
            assert data['kind'] == case['kind'], case
            assert data['key'] == case['key'], case
        elif case['status'] == 'ambiguous':
            assert result.returncode == 3, (case, result.stdout, result.stderr)
            assert 'AMBIGUOUS' in result.stderr
        else:
            assert result.returncode == 2, (case, result.stdout, result.stderr)
            assert 'NOT RESOLVED' in result.stderr


def test_plan_separates_runtime_parent_working_and_next_branch_policy():
    plan = json.loads((ROOT/'docs/PLAN.json').read_text(encoding='utf-8'))
    lineage = plan['canonical_lineage']
    assert lineage['runtime_base']['branch'] == 'api/fal-klein-001'
    assert lineage['current_package_base']['sha'] == 'a1de4b8fc551ba9b5ce3d1d88da7f1eaf378cd0e'
    assert lineage['working_branch'] == 'access/staff-delegation'
    assert lineage['next_branch_source'] == 'verified_working_head'
    assert plan['active_package'] == 'ACCESS-001'
    assert plan['next_package'] == 'SETTINGS-002'
    assert 'LINEAGE-001' in plan['packages']['ACCESS-001']['depends_on']
    assert plan['packages']['SETTINGS-001']['status'] == 'superseded_reference'
    assert plan['packages']['CATALOG-001']['status'] == 'superseded_reference'
    assert plan['packages']['SETTINGS-002']['status'] == 'planned_next'
    assert plan['packages']['CATALOG-002']['status'] == 'planned'
    assert plan['packages']['CATALOG-UI-002']['status'] == 'planned'
    assert plan['packages']['LOCAL-001']['depends_on'][-1] == 'CATALOG-002'
    parallel = next(item for item in plan['parallel_lineages'] if item['id'] == 'OPENROUTER-LINEAGE')
    assert parallel['status'] == 'reconciled_reference_only'
    assert parallel['do_not_continue_automatically'] is True


def test_live_admin_docs_use_post_reconciliation_package_ids():
    text = (ROOT/'docs/ADMIN.md').read_text(encoding='utf-8')
    assert 'SETTINGS-001' not in text and 'CATALOG-001' not in text
    assert 'SETTINGS-002' in text and 'CATALOG-UI-002' in text


def test_stable_docs_do_not_embed_mutable_sha_or_pr():
    sha = re.compile(r'\b[0-9a-f]{40}\b')
    pr = re.compile(r'\bPR\s*#\d+\b', re.I)
    for raw in ('AGENTS.md','README.md','docs/INDEX.md','docs/NEXT.md','docs/DEVELOPMENT.md','docs/DOCS_SYSTEM.md'):
        text = (ROOT/raw).read_text(encoding='utf-8')
        assert not sha.search(text), raw
        assert not pr.search(text), raw


def test_block_level_gallery_context_is_materially_smaller_than_old_feature_bundle():
    result = subprocess.run([sys.executable, str(ROOT/'tools/context.py'), '--task', 'сделай кнопку Скачать шире'],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'CONTEXT BLOCK: web.gallery.download_action' in result.stdout
    match = re.search(r'INITIAL DOCUMENT BYTES: (\d+)', result.stdout)
    assert match and int(match.group(1)) < 16000, result.stdout
    assert 'AssetPage.tsx' in result.stdout and 'Work.download' in result.stdout

def test_boundary_tests_use_explicit_utf8_reads():
    for path in (ROOT/'tests').glob('*boundaries.py'):
        text = path.read_text(encoding='utf-8')
        assert '.read_text()' not in text, path
