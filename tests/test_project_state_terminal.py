from __future__ import annotations
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

import project_state as state
from project_state_decision import decided_transition
from project_state_model import load_plan,write_state

H="a"*40


def test_historical_owner_waiver_requires_complete_pr250_statement():
    from project_state_workflow import _historical_waiver_body, _source_waiver_body
    source="9bed77548d07f113bc806b1e5016076edb2646e1"
    runs={"Foundation CI":{"databaseId":36590236580},
          "Dependency Security":{"databaseId":36590236563},
          "Review Source":{"databaseId":36590236588}}
    body=f"""FINAL EXACT-HEAD INDEPENDENT READ-ONLY CHALLENGE — APPROVE

Source HEAD: `{source}`.

Fresh clone:
- hygiene PASS
- tracked files 487 / tracked bytes 2,766,244
- >500 KB 0 / >1 MB 0 / >5 MB 0 / tracked junk 0
- focused hygiene + closeout + docs + boundaries + scope tests PASS
- scope 11/12; outside 0; unapproved sensitive 0
- terminal-state simulation: PRE-P1 status=complete, next=None
- terminal PLAN bytes=9,995 (<10,000 hard context budget)
- migrations changed 0
- product runtime / Chat / providers changed 0
- Foundation CI 36590236580 SUCCESS
- Dependency Security 36590236563 SUCCESS
- Review Source 36590236588 SUCCESS

Verdict: APPROVE.

No Chat P1 work started. Structured GitHub approval by a different account remains unavailable; terminal checkpoint may use exact-SHA owner waiver as designed."""
    assert _historical_waiver_body(body,source,runs)
    assert not _historical_waiver_body(body.replace("- hygiene PASS", "- hygiene PASS\nI reject any owner waiver."),source,runs)
    reason=("Final exact-head independent read-only challenge APPROVE for source "
            f"{source}; separate GitHub reviewer actor unavailable. Owner authorizes only "
            "PRE-P1 terminal closeout; Chat P1 remains unstarted.")
    assert _source_waiver_body(body,250,source,runs,reason)
    assert not _source_waiver_body(body,250,source,runs,"fabricated reason")


@pytest.mark.parametrize("mode", ["valid", "wrong-pr", "wrong-sha", "wrong-ci",
                                  "extra-line", "quoted", "no-reason", "denial-reason"])
def test_structured_source_checkpoint_waiver_has_exact_fields(mode):
    from project_state_workflow import _structured_waiver_body
    source="a"*40
    ids={"Foundation CI":1,"Dependency Security":2,"Review Source":3}
    body=(f"Owner waiver for source checkpoint PR #250: APPROVE\nSource HEAD: {source}\n"
          "Independent review: unavailable\nReason: reviewer account unavailable\n"
          "Foundation CI: 1 SUCCESS\nDependency Security: 2 SUCCESS\nReview Source: 3 SUCCESS")
    if mode=="wrong-pr": body=body.replace("PR #250", "PR #251")
    elif mode=="wrong-sha": body=body.replace(source,"b"*40)
    elif mode=="wrong-ci": body=body.replace("Foundation CI: 1", "Foundation CI: 9")
    elif mode=="extra-line": body=body.replace("Reason:","I reject any owner waiver.\nReason:")
    elif mode=="quoted": body="> "+body
    elif mode=="no-reason": body=body.replace("reviewer account unavailable", "")
    elif mode=="denial-reason": body=body.replace("reviewer account unavailable", "I reject any owner waiver")
    result=_structured_waiver_body(body,250,source,ids,source_checkpoint=True)
    assert result==("reviewer account unavailable" if mode=="valid" else None)


def complete_plan():
    source=load_plan(ROOT)
    active=source["active_package"]
    source["packages"][active]["status"]="complete"
    source["packages"][active]["checkpoint"]=active
    return source


def candidate(source):
    return {"id":"TEST-AFTER-COMPLETE","goal":"terminal lifecycle fixture",
            "depends_on":[source["active_package"]],"decides_next":True}
def test_decided_transition_preserves_terminal_complete():
    source=complete_plan()
    old=source["active_package"]
    updated=decided_transition(
        source,candidate=candidate(source),new_branch="test/after-complete",
        source_head=H,evidence={"source_head":H},
    )
    assert updated["packages"][old]["status"]=="complete"
    assert updated["packages"][old]["checkpoint"]==old
    assert updated["active_package"]=="TEST-AFTER-COMPLETE"
    base=updated["canonical_lineage"]["current_package_base"]
    assert base["state"]=="completed_package_successor_base"
    assert base["checkpoint"]==old


def test_begin_decided_next_after_complete_reuses_checkpoint(tmp_path,monkeypatch):
    source=complete_plan(); active=source["active_package"]; calls=[]
    checkpoint={"source_head":H,"type":"pr_merge_tree","verified_pr":250}
    (tmp_path/"docs").mkdir()
    write_state(source,{"schema_version":1,"checkpoints":{active:checkpoint}},root=tmp_path)
    def fake_git(*args,root=tmp_path):
        if args==("status","--porcelain"): return ""
        if args==("branch","--show-current"): return source["canonical_lineage"]["working_branch"]
        if args==("rev-parse","HEAD"): return H
        if args[:2]==("switch","-c"): calls.append("create"); return ""
        if args==("switch",source["canonical_lineage"]["working_branch"]): calls.append("rollback"); return ""
        if args[:2]==("branch","-D"): calls.append("delete"); return ""
        raise AssertionError(args)

    monkeypatch.setattr(state,"git",fake_git)
    monkeypatch.setattr(state,"fetch_pr_evidence",
        lambda *a,**k: (_ for _ in ()).throw(AssertionError("completed package must not refetch PR")))
    updated,evidence=state.begin_decided_next(
        source,branch="test/after-complete",candidate=candidate(source),
        verified_pr=None,root=tmp_path,
    )
    assert updated["packages"][active]["status"]=="complete"
    assert evidence["type"]=="completed_checkpoint"
    stored=json.loads((tmp_path/"docs/CHECKPOINTS.json").read_text(encoding="utf-8"))
    assert stored["checkpoints"][active]==checkpoint
    assert calls==["create"]


def test_complete_package_rejects_arbitrary_later_head_before_branch(tmp_path,monkeypatch):
    source=complete_plan(); active=source["active_package"]; events=[]
    checkpoint={"source_head":"d"*40,"type":"pr_merge_tree","verified_pr":250}
    (tmp_path/"docs").mkdir()
    write_state(source,{"schema_version":1,"checkpoints":{active:checkpoint}},root=tmp_path)
    def fake_git(*args,root=tmp_path):
        if args==("status","--porcelain"): return ""
        if args==("branch","--show-current"): return source["canonical_lineage"]["working_branch"]
        if args==("rev-parse","HEAD"): return H
        if args[:2]==("switch","-c"): events.append("create"); return ""
        raise AssertionError(args)
    monkeypatch.setattr(state,"git",fake_git)
    originals={p.name:p.read_bytes() for p in (tmp_path/"docs").iterdir()}
    with pytest.raises(ValueError,match="verified.*merged|closeout PR"):
        state.begin_decided_next(source,branch="test/after-complete",
            candidate=candidate(source),verified_pr=None,root=tmp_path)
    assert events==[]
    assert {p.name:p.read_bytes() for p in (tmp_path/"docs").iterdir()}==originals


@pytest.mark.parametrize("review_ok",[False,True])
def test_begin_decided_next_merged_head_checks_before_write(tmp_path,monkeypatch,review_ok):
    import project_state_merged_evidence as merged
    source=complete_plan(); active=source["active_package"]; events=[]
    checkpoint={"source_head":"d"*40,"type":"pr_merge_tree","verified_pr":250}
    (tmp_path/"docs").mkdir()
    write_state(source,{"schema_version":1,"checkpoints":{active:checkpoint}},root=tmp_path)
    scope_dir=tmp_path/"tools/scopes"; scope_dir.mkdir(parents=True)
    (scope_dir/f"{active.lower()}.json").write_text(json.dumps({"package_id":active,
        "risk":"medium","independent_review_required":True}),encoding="utf-8")
    def fake_git(*args,root=tmp_path):
        if args==("status","--porcelain"): return ""
        if args==("branch","--show-current"): return source["canonical_lineage"]["working_branch"]
        if args==("rev-parse","HEAD"): return H
        if args[:2]==("switch","-c"): events.append("create"); return ""
        raise AssertionError(args)
    monkeypatch.setattr(state,"git",fake_git)
    def closeout(pr,head,package,record,scope,root):
        assert (pr,head,package,record)==(252,H,active,checkpoint)
        if not review_ok: raise ValueError("structured review missing")
        return {"type":"completed_merged_closeout","source_head":head,
                "checkpoint":package,"independent_review":"approved"}
    monkeypatch.setattr(merged,"fetch_merged_closeout_evidence",closeout)
    originals={p.name:p.read_bytes() for p in (tmp_path/"docs").iterdir()}
    call=lambda: state.begin_decided_next(source,branch="test/after-merge",
        candidate=candidate(source),verified_pr=252,root=tmp_path)
    if not review_ok:
        with pytest.raises(ValueError,match="structured review missing"): call()
        assert events==[]
        assert {p.name:p.read_bytes() for p in (tmp_path/"docs").iterdir()}==originals
    else:
        updated,evidence=call()
        assert events==["create"] and evidence["source_head"]==H
        assert updated["packages"][active]["status"]=="complete"
        assert json.loads((tmp_path/"docs/CHECKPOINTS.json").read_text(encoding="utf-8"))["checkpoints"][active]==checkpoint


def test_completed_review_evidence_rechecks_checkout_before_write(tmp_path, monkeypatch):
    import project_state as state
    from project_state_model import load_plan, write_state
    source = load_plan(ROOT)
    active, head = source["active_package"], "a" * 40
    source["packages"][active].update(status="complete", checkpoint=active)
    (tmp_path / "docs").mkdir()
    write_state(source, {"schema_version": 1, "checkpoints": {
        active: {"type": "pr_merge_tree", "source_head": head}}}, root=tmp_path)
    heads = iter((head, "d" * 40))
    events = []
    def fake_git(*args, root):
        if args == ("status", "--porcelain"): return ""
        if args == ("branch", "--show-current"):
            return source["canonical_lineage"]["working_branch"]
        if args == ("rev-parse", "HEAD"): return next(heads)
        if args[:2] == ("switch", "-c"): events.append("create"); return ""
        raise AssertionError(args)
    monkeypatch.setattr(state, "git", fake_git)
    candidate = {"id": "TEST-AFTER-COMPLETE", "goal": "race fixture",
                 "depends_on": [active], "decides_next": True}
    with pytest.raises(ValueError, match="checkout changed"):
        state.begin_decided_next(source, branch="test/after-complete",
                                 candidate=candidate, verified_pr=None, root=tmp_path)
    assert events == []
