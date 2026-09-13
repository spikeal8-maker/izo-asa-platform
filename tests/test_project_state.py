"""Continuation safety, checkpoint isolation and GitHub evidence binding."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from project_state import dependency_problems, render_current, transition, validate_pr_evidence  # noqa: E402


def plan():
    return json.loads((ROOT / "docs/PLAN.json").read_text(encoding="utf-8"))


def evidence(head="a" * 40):
    return {
        "type": "pr_merge_tree", "source_head": head, "verified_pr": 99,
        "base_head": "b" * 40, "tested_merge_tree": "c" * 40,
        "workflows": {"Foundation CI": 1, "Dependency Security": 2, "Review Source": 3},
    }


def transitionable_plan():
    source = plan()
    active = source["active_package"]
    source["packages"]["TEST-NEXT"] = {
        "status": "planned_next", "depends_on": [active, "AUTH-002"], "decides_next": True}
    source["next_package"] = "TEST-NEXT"
    return source


def test_current_is_rendered_from_machine_plan():
    source = plan()
    text = render_current(source)
    lineage = source["canonical_lineage"]
    assert f"working_branch={lineage['working_branch']}" in text
    assert f"active_package={source['active_package']}" in text
    assert "next_package=NONE" in text
    assert "не выбирать его вручную как base следующего package" in text


def test_pr_merge_tree_evidence_binds_source_head_and_required_workflows():
    head = "a" * 40
    runs = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request", "conclusion": "success", "databaseId": 11},
        {"name": "Dependency Security", "headSha": head, "event": "pull_request", "conclusion": "success", "databaseId": 12},
        {"name": "Review Source", "headSha": head, "event": "pull_request", "conclusion": "success", "databaseId": 13},
    ]
    result = validate_pr_evidence(
        pr={"headRefOid": head, "baseRefOid": "b" * 40, "state": "OPEN"}, runs=runs,
        merge_sha="c" * 40, merge_commit={"parents": [{"sha": "b" * 40}, {"sha": head}]},
        expected_head=head, pr_number=99, foundation_tree="c" * 40)
    assert result["type"] == "pr_merge_tree"
    assert result["source_head"] == head
    assert result["workflows"]["Foundation CI"] == 11


def test_pr_evidence_rejects_wrong_sha_missing_workflow_and_stale_tree():
    head = "a" * 40
    with pytest.raises(ValueError, match="head"):
        validate_pr_evidence(pr={"headRefOid": "d" * 40, "baseRefOid": "b" * 40, "state": "OPEN"},
            runs=[], merge_sha="c" * 40, merge_commit={"parents": [{"sha": head}]},
            expected_head=head, pr_number=99, foundation_tree="c" * 40)
    runs = [{"name": "Foundation CI", "headSha": head, "event": "pull_request",
             "conclusion": "success", "databaseId": 1}]
    with pytest.raises(ValueError, match="Dependency Security"):
        validate_pr_evidence(pr={"headRefOid": head, "baseRefOid": "b" * 40, "state": "OPEN"},
            runs=runs, merge_sha="c" * 40,
            merge_commit={"parents": [{"sha": "b" * 40}, {"sha": head}]},
            expected_head=head, pr_number=99, foundation_tree="c" * 40)
    runs = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request", "conclusion": "success", "databaseId": 11},
        {"name": "Dependency Security", "headSha": head, "event": "pull_request", "conclusion": "success", "databaseId": 12},
        {"name": "Review Source", "headSha": head, "event": "pull_request", "conclusion": "success", "databaseId": 13},
    ]
    with pytest.raises(ValueError, match="tested merge tree"):
        validate_pr_evidence(pr={"headRefOid": head, "baseRefOid": "b" * 40, "state": "OPEN"}, runs=runs,
            merge_sha="c" * 40, merge_commit={"parents": [{"sha": "b" * 40}, {"sha": head}]},
            expected_head=head, pr_number=99, foundation_tree="d" * 40)


def test_transition_records_checkpoint_reference_not_full_evidence():
    source = transitionable_plan()
    active = source["active_package"]
    head = "a" * 40
    assert dependency_problems(source, "TEST-NEXT", finishing=active) == []
    updated = transition(source, activate="TEST-NEXT", next_id=None,
                         new_branch="test/next", source_head=head, evidence=evidence(head))
    assert updated["packages"][active]["status"] == "technical_pass"
    assert updated["packages"][active]["checkpoint"] == active
    assert "evidence" not in updated["packages"][active]
    assert updated["active_package"] == "TEST-NEXT"


def test_transition_rejects_unready_dependency():
    source = transitionable_plan()
    source["packages"]["AUTH-002"]["status"] = "planned"
    with pytest.raises(ValueError, match="AUTH-002"):
        transition(source, activate="TEST-NEXT", next_id=None, new_branch="test/next",
                   source_head="a" * 40, evidence=evidence())


def test_machine_plan_stays_compact_enough_for_agent_context():
    text = (ROOT / "docs/PLAN.json").read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 10_000
    assert len(text.splitlines()) < 140


def test_begin_next_rolls_back_branch_state_and_checkpoint_on_write_failure(tmp_path, monkeypatch):
    import project_state as state
    source = transitionable_plan()
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "PLAN.json").write_bytes(b"old-plan")
    (docs / "CURRENT.md").write_bytes(b"old-current")
    (docs / "CHECKPOINTS.json").write_bytes(b'{"schema_version":1,"checkpoints":{}}')
    calls = []

    def fake_git(*args, root=tmp_path):
        if args == ("status", "--porcelain"): return ""
        if args == ("branch", "--show-current"): return source["canonical_lineage"]["working_branch"]
        if args == ("rev-parse", "HEAD"): return "a" * 40
        if args[:2] == ("switch", "-c"): calls.append("create"); return ""
        if args == ("switch", source["canonical_lineage"]["working_branch"]): calls.append("rollback"); return ""
        if args[:2] == ("branch", "-D"): calls.append("delete"); return ""
        raise AssertionError(args)

    monkeypatch.setattr(state, "git", fake_git)
    monkeypatch.setattr(state, "fetch_pr_evidence", lambda *a, **k: evidence("a" * 40))

    def broken_write(updated, checkpoints=None, root=tmp_path):
        (root / "docs/PLAN.json").write_bytes(b"partial")
        (root / "docs/CHECKPOINTS.json").write_bytes(b"partial")
        raise OSError("disk failure")

    monkeypatch.setattr(state, "write_state", broken_write)
    with pytest.raises(OSError, match="disk failure"):
        state.begin_next(source, branch="test/next", activate="TEST-NEXT", next_id=None,
                         verified_pr=99, root=tmp_path)
    assert (docs / "PLAN.json").read_bytes() == b"old-plan"
    assert (docs / "CURRENT.md").read_bytes() == b"old-current"
    assert (docs / "CHECKPOINTS.json").read_bytes() == b'{"schema_version":1,"checkpoints":{}}'
    assert calls == ["create", "rollback", "delete"]


def test_transition_requires_direct_dependency_on_finishing_package():
    source = transitionable_plan()
    source["packages"]["TEST-NEXT"]["depends_on"] = ["AUTH-002"]
    with pytest.raises(ValueError, match="next_package must directly depend on the active package"):
        import project_state as state
        state.validate_plan(source)


def test_transition_rejects_completed_or_unrelated_next_package():
    source = transitionable_plan()
    source["packages"]["AUTH-001"]["depends_on"] = ["TEST-NEXT"]
    with pytest.raises(ValueError, match="not eligible from status technical_pass"):
        transition(source, activate="TEST-NEXT", next_id="AUTH-001", new_branch="test/next",
                   source_head="a" * 40, evidence=evidence())
