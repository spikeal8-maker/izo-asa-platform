"""Frozen-checkpoint state transition rules."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from project_state import render_current, start_transition  # noqa: E402


def plan():
    return json.loads((ROOT/'docs/PLAN.json').read_text(encoding='utf-8'))


def test_current_is_generated_from_explicit_branch_roles():
    text = render_current(plan())
    assert 'runtime_base=api/fal-klein-001@faec39d6' in text
    assert 'branch_from=docs/agent-development-system@001edb9' in text
    assert 'working_branch=docs/maintenance-precision' in text
    assert 'active_package=DOC-004B' in text


def test_next_branch_advances_state_without_mutating_frozen_checkpoint():
    source = plan()
    frozen = 'a' * 40
    source['canonical_lineage']['working_branch'] = 'docs/maintenance-precision'
    source['next_package'] = 'LINEAGE-001'
    source['packages']['LINEAGE-001']['status'] = 'planned_next'
    updated = start_transition(source, current_branch='lineage/reconcile', current_head=frozen,
                               activate='LINEAGE-001', next_id='PROFILE-001', foundation_ci=12345)
    assert source['active_package'] == 'DOC-004B'
    assert updated['packages']['DOC-004B']['status'] == 'technical_pass'
    assert updated['packages']['DOC-004B']['evidence']['head'] == frozen
    assert updated['active_package'] == 'LINEAGE-001'
    assert updated['canonical_lineage']['branch_from']['branch'] == 'docs/maintenance-precision'
    assert updated['canonical_lineage']['branch_from']['sha'] == frozen
    assert updated['canonical_lineage']['working_branch'] == 'lineage/reconcile'


def test_transition_refuses_reusing_frozen_branch():
    source = plan()
    try:
        start_transition(source, current_branch=source['canonical_lineage']['working_branch'], current_head='b'*40,
                         activate='LINEAGE-001', next_id='PROFILE-001', foundation_ci=1)
    except ValueError as exc:
        assert 'new branch' in str(exc)
    else:
        raise AssertionError('frozen branch reuse must be rejected')


def test_machine_plan_stays_compact_enough_for_agent_context():
    text = (ROOT/'docs/PLAN.json').read_text(encoding='utf-8')
    assert len(text.encode('utf-8')) < 10000
    assert len(text.splitlines()) < 140


def test_decision_stage_may_start_without_inventing_next_package():
    source = plan()
    updated = start_transition(source, current_branch='lineage/reconcile', current_head='c'*40,
                               activate='LINEAGE-001', next_id=None, foundation_ci=222)
    assert updated['active_package'] == 'LINEAGE-001'
    assert updated['next_package'] is None
    assert updated['packages']['LINEAGE-001']['decides_next'] is True
