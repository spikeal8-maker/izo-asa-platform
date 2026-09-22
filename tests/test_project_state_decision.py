"""Dynamic decides_next registration, evidence ordering and rollback."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from project_state_decision import decided_transition, validate_decided_candidate  # noqa: E402
from project_state_evidence import validate_pr_evidence  # noqa: E402


def base_plan():
    return json.loads((ROOT / "docs/PLAN.json").read_text(encoding="utf-8"))


def candidate(source=None, package_id="TEST-DYNAMIC"):
    source = source or base_plan()
    return {"id": package_id, "goal": "bounded control-plane fixture",
            "depends_on": [source["active_package"]], "decides_next": True}


def evidence(head="a" * 40):
    return {"type": "pr_merge_tree", "source_head": head, "verified_pr": 99,
            "base_head": "b" * 40, "tested_merge_tree": "c" * 40,
            "workflows": {"Foundation CI": 1, "Dependency Security": 2, "Review Source": 3},
            "independent_review": "unavailable", "owner_waiver": True,
            "owner_actor": "owner", "owner_waiver_source": head, "owner_waiver_reason": "fixture"}


def test_decides_next_null_can_register_and_activate_atomically():
    source = base_plan()
    assert source["next_package"] is None
    head = "a" * 40
    updated = decided_transition(source, candidate=candidate(source), new_branch="test/dynamic",
                                 source_head=head, evidence=evidence(head))
    old = source["active_package"]
    assert updated["packages"][old]["status"] == "technical_pass"
    assert updated["packages"][old]["checkpoint"] == old
    assert updated["packages"]["TEST-DYNAMIC"]["status"] == "active"
    assert updated["active_package"] == "TEST-DYNAMIC" and updated["next_package"] is None
    assert updated["canonical_lineage"]["current_package_base"]["sha"] == head


def test_dynamic_candidate_rejects_non_decider_bad_fields_and_dependencies():
    source = base_plan(); source["packages"][source["active_package"]]["decides_next"] = False
    with pytest.raises(ValueError, match="decide next"):
        validate_decided_candidate(source, candidate(source))
    source = base_plan(); bad = candidate(source); bad["unexpected"] = True
    with pytest.raises(ValueError, match="fields invalid"): validate_decided_candidate(source, bad)
    bad = candidate(source); bad["depends_on"] = ["AUTH-002"]
    with pytest.raises(ValueError, match="directly depend"): validate_decided_candidate(source, bad)
    bad = candidate(source); bad["depends_on"] = [source["active_package"], "PROFILE-001"]
    with pytest.raises(ValueError, match="not ready"): validate_decided_candidate(source, bad)


def test_existing_package_must_be_compatible_planned_record():
    source = base_plan()
    source["packages"]["TEST-PLANNED"] = {
        "status": "planned", "goal": "same", "depends_on": [source["active_package"]],
        "decides_next": True}
    validate_decided_candidate(source, {
        "id": "TEST-PLANNED", "goal": "same", "depends_on": [source["active_package"]],
        "decides_next": True})
    with pytest.raises(ValueError, match="conflicts"):
        validate_decided_candidate(source, {
            "id": "TEST-PLANNED", "goal": "different",
            "depends_on": [source["active_package"]], "decides_next": True})


def test_waiver_never_overrides_wrong_head_or_failed_ci():
    head = "a" * 40
    runs = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "conclusion": "success", "databaseId": 1},
        {"name": "Review Source", "headSha": head, "event": "pull_request",
         "conclusion": "success", "databaseId": 2}]
    with pytest.raises(ValueError, match="Dependency Security"):
        validate_pr_evidence(
            pr={"headRefOid": head, "baseRefOid": "b" * 40, "state": "OPEN"}, runs=runs,
            merge_sha="c" * 40, merge_commit={"parents": [{"sha": "b" * 40}, {"sha": head}]},
            expected_head=head, pr_number=99, foundation_tree="c" * 40)
    with pytest.raises(ValueError, match="head"):
        validate_pr_evidence(
            pr={"headRefOid": "d" * 40, "baseRefOid": "b" * 40, "state": "OPEN"}, runs=[],
            merge_sha="c" * 40, merge_commit={"parents": [{"sha": head}]},
            expected_head=head, pr_number=99, foundation_tree="c" * 40)


def _write_docs(root: Path, source: dict):
    docs = root / "docs"; docs.mkdir()
    (docs / "PLAN.json").write_text(json.dumps(source), encoding="utf-8")
    (docs / "CURRENT.md").write_text("old-current", encoding="utf-8")
    (docs / "CHECKPOINTS.json").write_text('{"schema_version":1,"checkpoints":{}}', encoding="utf-8")


def test_failed_ci_stops_before_branch_creation(tmp_path, monkeypatch):
    import project_state as state
    source = base_plan(); _write_docs(tmp_path, source); calls = []
    def fake_git(*args, root=tmp_path):
        if args == ("status", "--porcelain"): return ""
        if args == ("branch", "--show-current"): return source["canonical_lineage"]["working_branch"]
        if args == ("rev-parse", "HEAD"): return "a" * 40
        if args[:2] == ("switch", "-c"): calls.append("create"); return ""
        raise AssertionError(args)
    monkeypatch.setattr(state, "git", fake_git)
    monkeypatch.setattr(state, "fetch_pr_evidence",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("required workflow failed")))
    with pytest.raises(ValueError, match="workflow"):
        state.begin_decided_next(
            source, branch="test/dynamic", candidate=candidate(source), verified_pr=99,
            owner_waiver=True, independent_review_unavailable=True,
            owner_waiver_source="a" * 40, owner_waiver_reason="fixture", root=tmp_path)
    assert calls == []


def test_failure_after_branch_creation_rolls_back_files_and_branch(tmp_path, monkeypatch):
    import project_state as state
    source = base_plan(); _write_docs(tmp_path, source)
    originals = {name: (tmp_path / "docs" / name).read_bytes()
                 for name in ("PLAN.json", "CURRENT.md", "CHECKPOINTS.json")}
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
    monkeypatch.setattr(state, "fetch_pr_evidence", lambda *a, **k: evidence())
    monkeypatch.setattr(state, "fetch_review_evidence", lambda *a, **k: {
        "independent_review": "unavailable", "owner_waiver": True, "owner_actor": "owner",
        "owner_waiver_source": "a" * 40, "owner_waiver_reason": "fixture"})
    def broken_write(updated, checkpoints=None, root=tmp_path):
        for name in originals: (root / "docs" / name).write_text("partial", encoding="utf-8")
        raise OSError("disk failure")
    monkeypatch.setattr(state, "write_state", broken_write)
    with pytest.raises(OSError, match="disk failure"):
        state.begin_decided_next(
            source, branch="test/dynamic", candidate=candidate(source), verified_pr=99,
            owner_waiver=True, independent_review_unavailable=True,
            owner_waiver_source="a" * 40, owner_waiver_reason="fixture", root=tmp_path)
    for name, data in originals.items(): assert (tmp_path / "docs" / name).read_bytes() == data
    assert calls == ["create", "rollback", "delete"]


def test_legacy_begin_next_still_works(tmp_path, monkeypatch):
    import project_state as state
    source = base_plan(); active = source["active_package"]
    source["packages"]["TEST-LEGACY"] = {
        "status": "planned_next", "depends_on": [active], "decides_next": True}
    source["next_package"] = "TEST-LEGACY"; _write_docs(tmp_path, source); events = []
    def fake_git(*args, root=tmp_path):
        if args == ("status", "--porcelain"): return ""
        if args == ("branch", "--show-current"): return source["canonical_lineage"]["working_branch"]
        if args == ("rev-parse", "HEAD"): return "a" * 40
        if args[:2] == ("switch", "-c"): events.append("create"); return ""
        raise AssertionError(args)
    monkeypatch.setattr(state, "git", fake_git)
    monkeypatch.setattr(state, "fetch_pr_evidence", lambda *a, **k: evidence())
    monkeypatch.setattr(state, "fetch_review_evidence",
                        lambda *a, **k: {"independent_review": "not_required", "owner_waiver": False})
    updated, _ = state.begin_next(
        source, branch="test/legacy", activate="TEST-LEGACY", next_id=None,
        verified_pr=99, root=tmp_path)
    assert updated["active_package"] == "TEST-LEGACY" and events == ["create"]
