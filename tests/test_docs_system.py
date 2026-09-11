"""DOC-004: documentation is executable routing, not a second stale roadmap."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_context(*args: str) -> str:
    result = subprocess.run([sys.executable, str(ROOT/'tools/context.py'), *args],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_documentation_validator_passes():
    result = subprocess.run([sys.executable, str(ROOT/'tools/check_docs.py')],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DOCS CHECK OK' in result.stdout


def test_context_router_localizes_typical_small_changes():
    cases = {
        'сделай кнопку Скачать в галерее шире на телефоне': 'web.gallery',
        'поменяй текст подтверждения генерации в студии': 'web.studio',
        'исправь пароль и сессии на странице аккаунта': 'web.accounts',
        'изменить тарифный лимит доступа к модели': 'api.entitlements',
        'fal уже принял запрос, исправь отмену provider request': 'api.provider_execution',
        'проверь docker compose и egress worker': 'ops.runtime',
    }
    for task, route in cases.items():
        output = run_context('--task', task)
        assert f'CONTEXT ROUTE: {route}' in output

def test_plan_has_one_canonical_line_and_blocks_parallel_continuation():
    plan = json.loads((ROOT/'docs/PLAN.json').read_text(encoding='utf-8'))
    assert plan['active_package'] == 'DOC-004'
    assert plan['next_package'] == 'LINEAGE-001'
    assert plan['canonical_lineage']['baseline_branch'] == 'api/fal-klein-001'
    active = [key for key, value in plan['packages'].items() if value['status'] == 'active']
    assert active == ['DOC-004']
    lineage = next(item for item in plan['parallel_lineages'] if item['id'] == 'OPENROUTER-LINEAGE')
    assert lineage['do_not_continue_automatically'] is True
    assert {19, 20, 21}.issubset(set(lineage['prs']))
    assert plan['packages']['SETTINGS-001']['status'] == 'parallel_lineage_only'
    assert plan['packages']['CATALOG-001']['status'] == 'parallel_lineage_only'


def test_stable_entry_documents_do_not_embed_current_project_head():
    for raw in ('AGENTS.md', 'docs/INDEX.md', 'docs/DEVELOPMENT.md', 'docs/DOCS_SYSTEM.md'):
        text = (ROOT/raw).read_text(encoding='utf-8')
        assert 'faec39d6ae0b4f035ef0f86114494789acde3b46' not in text
        assert 'Следующий шаг — UX-001' not in text
        assert 'tools/scopes/ux-001.json' not in text


def test_context_map_uses_existing_paths_only():
    context = json.loads((ROOT/'docs/CONTEXT_MAP.json').read_text(encoding='utf-8'))
    for route in context['routes'].values():
        for field in ('read_first', 'tests', 'expand_if_needed', 'do_not_read_by_default'):
            for raw in route.get(field, []):
                assert (ROOT/raw).exists(), (field, raw)
