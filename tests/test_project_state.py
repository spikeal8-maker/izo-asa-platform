"""Continuation safety and GitHub evidence binding."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from project_state import (  # noqa: E402
    dependency_problems,
    render_current,
    transition,
    validate_pr_evidence,
)


def plan():
    return json.loads((ROOT/'docs/PLAN.json').read_text(encoding='utf-8'))


def evidence(head='a'*40):
    return {
        'type': 'pr_merge_tree', 'source_head': head, 'verified_pr': 32,
        'base_head': 'b'*40, 'tested_merge_tree': 'c'*40,
        'workflows': {'Foundation CI': 1, 'Dependency Security': 2, 'Review Source': 3},
    }


def transitionable_plan():
    source = plan()
    source['next_package'] = 'GUEST-001'
    source['packages']['GUEST-001']['status'] = 'planned_next'
    source['packages']['GUEST-001']['decides_next'] = True
    return source


def test_current_uses_owner_reprioritized_working_head_policy():
    text = render_current(plan())
    assert 'runtime_base=api/fal-klein-001@faec39d6' in text
    assert 'current_package_base=settings/plan-policy@220d302' in text
    assert 'working_branch=ux/product-shell' in text
    assert 'active_package=UX-002' in text
    assert 'next_package=NONE' in text
    assert 'не выбирать его вручную как base следующего package' in text


def test_pr_merge_tree_evidence_binds_source_head_and_required_workflows():
    head = 'a' * 40
    runs = [
        {'name': 'Foundation CI', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 11},
        {'name': 'Dependency Security', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 12},
        {'name': 'Review Source', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 13},
    ]
    result = validate_pr_evidence(
        pr={'headRefOid': head, 'baseRefOid': 'b'*40, 'state': 'OPEN'}, runs=runs,
        merge_sha='c'*40, merge_commit={'parents': [{'sha': 'b'*40}, {'sha': head}]},
        expected_head=head, pr_number=32, foundation_tree='c'*40,
    )
    assert result['type'] == 'pr_merge_tree'
    assert result['source_head'] == head
    assert result['workflows']['Foundation CI'] == 11


def test_pr_evidence_rejects_wrong_sha_or_missing_required_workflow():
    head = 'a' * 40
    with pytest.raises(ValueError, match='head'):
        validate_pr_evidence(
            pr={'headRefOid': 'd'*40, 'baseRefOid': 'b'*40, 'state': 'OPEN'}, runs=[],
            merge_sha='c'*40, merge_commit={'parents': [{'sha': head}]},
            expected_head=head, pr_number=32, foundation_tree='c'*40,
        )
    runs = [{'name': 'Foundation CI', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 1}]
    with pytest.raises(ValueError, match='Dependency Security'):
        validate_pr_evidence(
            pr={'headRefOid': head, 'baseRefOid': 'b'*40, 'state': 'OPEN'}, runs=runs,
            merge_sha='c'*40, merge_commit={'parents': [{'sha': head}]},
            expected_head=head, pr_number=32, foundation_tree='c'*40,
        )


def test_pr_evidence_rejects_stale_merge_tree():
    head = 'a' * 40
    runs = [
        {'name': 'Foundation CI', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 11},
        {'name': 'Dependency Security', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 12},
        {'name': 'Review Source', 'headSha': head, 'event': 'pull_request', 'conclusion': 'success', 'databaseId': 13},
    ]
    with pytest.raises(ValueError, match='tested merge tree'):
        validate_pr_evidence(
            pr={'headRefOid': head, 'baseRefOid': 'b'*40, 'state': 'OPEN'}, runs=runs,
            merge_sha='c'*40, merge_commit={'parents': [{'sha': 'b'*40}, {'sha': head}]},
            expected_head=head, pr_number=32, foundation_tree='d'*40,
        )


def test_transition_can_start_owner_selected_package_after_ux_acceptance():
    source = transitionable_plan()
    head = 'a' * 40
    assert dependency_problems(source, 'GUEST-001', finishing='UX-002') == []
    updated = transition(source, activate='GUEST-001', next_id=None, new_branch='guest/first-trial',
                         source_head=head, evidence=evidence(head))
    assert updated['packages']['UX-002']['status'] == 'technical_pass'
    assert updated['packages']['UX-002']['evidence']['source_head'] == head
    assert updated['active_package'] == 'GUEST-001'
    assert updated['next_package'] is None


def test_transition_rejects_unready_dependency():
    source = transitionable_plan()
    source['packages']['JOBS-001']['status'] = 'planned'
    with pytest.raises(ValueError, match='JOBS-001'):
        transition(source, activate='GUEST-001', next_id=None, new_branch='guest/first-trial',
                   source_head='a'*40, evidence=evidence())


def test_machine_plan_stays_compact_enough_for_agent_context():
    text = (ROOT/'docs/PLAN.json').read_text(encoding='utf-8')
    assert len(text.encode('utf-8')) < 10000
    assert len(text.splitlines()) < 140


def test_begin_next_rolls_back_branch_and_state_on_write_failure(tmp_path, monkeypatch):
    import project_state as state
    source = transitionable_plan()
    docs = tmp_path/'docs'; docs.mkdir()
    (docs/'PLAN.json').write_bytes(b'old-plan')
    (docs/'CURRENT.md').write_bytes(b'old-current')
    calls=[]
    def fake_git(*args, root=tmp_path):
        if args == ('status','--porcelain'): return ''
        if args == ('branch','--show-current'): return 'ux/product-shell'
        if args == ('rev-parse','HEAD'): return 'a'*40
        if args[:2] == ('switch','-c'): calls.append('create'); return ''
        if args == ('switch','ux/product-shell'): calls.append('rollback'); return ''
        if args[:2] == ('branch','-D'): calls.append('delete'); return ''
        raise AssertionError(args)
    monkeypatch.setattr(state, 'git', fake_git)
    monkeypatch.setattr(state, 'fetch_pr_evidence', lambda *a, **k: evidence('a'*40))
    def broken_write(updated, root=tmp_path):
        (root/'docs/PLAN.json').write_bytes(b'partial')
        raise OSError('disk failure')
    monkeypatch.setattr(state, 'write_state', broken_write)
    with pytest.raises(OSError, match='disk failure'):
        state.begin_next(source, branch='guest/first-trial', activate='GUEST-001', next_id=None,
                         verified_pr=32, root=tmp_path)
    assert (docs/'PLAN.json').read_bytes() == b'old-plan'
    assert (docs/'CURRENT.md').read_bytes() == b'old-current'
    assert calls == ['create','rollback','delete']


def test_transition_requires_direct_dependency_on_finishing_package():
    source = transitionable_plan()
    source['packages']['GUEST-001']['depends_on'] = ['AUTH-002','JOBS-001','IMAGE-001']
    with pytest.raises(ValueError, match='next_package must directly depend on the active package'):
        import project_state as state
        state.validate_plan(source)


def test_transition_rejects_completed_or_unrelated_next_package():
    source = transitionable_plan()
    with pytest.raises(ValueError, match='not eligible from status technical_pass'):
        transition(source, activate='GUEST-001', next_id='AUTH-001', new_branch='guest/first-trial',
                   source_head='a'*40, evidence=evidence())
