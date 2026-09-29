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
    checkpoint={"source_head":"d"*40,"type":"pr_merge_tree","verified_pr":250}
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
