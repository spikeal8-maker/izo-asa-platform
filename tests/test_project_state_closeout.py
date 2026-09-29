from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_state_closeout as closeout
from project_state_model import load_plan, render_current, validate_plan

H = "a" * 40


def evidence(head=H):
    return {
        "type": "pr_merge_tree",
        "source_head": head,
        "verified_pr": 99,
        "base_head": "b" * 40,
        "tested_merge_tree": "c" * 40,
        "workflows": {
            "Foundation CI": 1,
            "Dependency Security": 2,
            "Review Source": 3,
        },
        "independent_review": "unavailable",
        "owner_waiver": True,
        "owner_actor": "owner",
        "owner_waiver_source": head,
        "owner_waiver_reason": "fixture",
    }


def active_plan():
    plan = load_plan()
    active = plan["active_package"]
    plan["packages"][active]["status"] = "active"
    plan["next_package"] = None
    return plan


def test_complete_transition_freezes_without_starting_successor():
    plan = active_plan()
    active = plan["active_package"]
    updated = closeout.complete_transition(plan, evidence())
    assert updated["active_package"] == active
    assert updated["packages"][active]["status"] == "complete"
    assert updated["packages"][active]["checkpoint"] == active
    assert updated["next_package"] is None
    assert "Завершённый пакет" in render_current(updated)
    validate_plan(updated)


def test_complete_transition_rejects_selected_successor():
    plan = active_plan()
    plan["packages"]["TEST-NEXT"] = {
        "status": "planned_next",
        "depends_on": [plan["active_package"]],
        "decides_next": True,
    }
    plan["next_package"] = "TEST-NEXT"
    with pytest.raises(ValueError, match="next_package"):
        closeout.complete_transition(plan, evidence())


def test_complete_transition_rejects_non_active_package():
    plan = active_plan()
    plan["packages"][plan["active_package"]]["status"] = "complete"
    validate_plan(plan)
    with pytest.raises(ValueError, match="active package"):
        closeout.complete_transition(plan, evidence())


def test_closeout_rolls_back_state_and_branch_on_write_failure(tmp_path, monkeypatch):
    plan = active_plan()
    docs = tmp_path / "docs"
    docs.mkdir()
    for name, data in {
        "PLAN.json": json.dumps(plan),
        "CURRENT.md": "old-current",
        "CHECKPOINTS.json": '{"schema_version":1,"checkpoints":{}}',
    }.items():
        (docs / name).write_text(data, encoding="utf-8")
    scopes = tmp_path / "tools" / "scopes"
    scopes.mkdir(parents=True)
    (scopes / f"{plan['active_package'].lower()}.json").write_text(
        json.dumps({"package_id": plan["active_package"], "risk": "medium"}),
        encoding="utf-8",
    )
    calls = []

    def fake_git(*args, root=tmp_path):
        if args == ("status", "--porcelain"):
            return ""
        if args == ("branch", "--show-current"):
            return plan["canonical_lineage"]["working_branch"]
        if args == ("rev-parse", "HEAD"):
            return H
        if args[:2] == ("switch", "-c"):
            calls.append("create")
            return ""
        if args == ("switch", plan["canonical_lineage"]["working_branch"]):
            calls.append("rollback")
            return ""
        if args[:2] == ("branch", "-D"):
            calls.append("delete")
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(closeout, "git", fake_git)
    monkeypatch.setattr(closeout, "fetch_pr_evidence", lambda *a, **k: evidence())
    monkeypatch.setattr(
        closeout, "fetch_review_evidence",
        lambda *a, **k: {
            "independent_review": "unavailable",
            "owner_waiver": True,
            "owner_waiver_source": H,
            "owner_waiver_reason": "fixture",
        },
    )

    originals = {p.name: p.read_bytes() for p in docs.iterdir()}

    def broken_write(updated, checkpoints=None, root=tmp_path):
        (root / "docs" / "PLAN.json").write_text("partial", encoding="utf-8")
        raise OSError("disk failure")

    monkeypatch.setattr(closeout, "write_state", broken_write)
    with pytest.raises(OSError, match="disk failure"):
        closeout.complete_current(
            plan, branch="state/complete", verified_pr=99,
            owner_waiver=True, independent_review_unavailable=True,
            owner_waiver_source=H, owner_waiver_reason="fixture", root=tmp_path,
        )
    for name, data in originals.items():
        assert (docs / name).read_bytes() == data
    assert calls == ["create", "rollback", "delete"]
