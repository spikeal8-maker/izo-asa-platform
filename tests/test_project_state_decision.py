from __future__ import annotations
import json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from project_state_decision import decided_transition,validate_decided_candidate
from project_state_evidence import validate_pr_evidence
H,B,C="a"*40,"b"*40,"c"*40
def base_plan(): return json.loads((ROOT/"docs/PLAN.json").read_text(encoding="utf-8"))
def candidate(s=None,package_id="TEST-DYNAMIC"):
    s=s or base_plan(); return {"id":package_id,"goal":"bounded control-plane fixture","depends_on":[s["active_package"]],"decides_next":True}
def evidence(head=H):
    return {"type":"pr_merge_tree","source_head":head,"verified_pr":99,"base_head":B,"tested_merge_tree":C,"workflows":{"Foundation CI":1,"Dependency Security":2,"Review Source":3},"independent_review":"unavailable","owner_waiver":True,"owner_actor":"owner","owner_waiver_source":head,"owner_waiver_reason":"fixture"}
def _scope(s,risk="medium"): return {"package_id":s["active_package"],"risk":risk}
def _write_docs(root,s,with_scope=True):
    docs=root/"docs"; docs.mkdir(); (docs/"PLAN.json").write_text(json.dumps(s),encoding="utf-8"); (docs/"CURRENT.md").write_text("old-current",encoding="utf-8"); (docs/"CHECKPOINTS.json").write_text('{"schema_version":1,"checkpoints":{}}',encoding="utf-8")
    if with_scope:
        p=root/"tools/scopes"; p.mkdir(parents=True); (p/f"{s['active_package'].lower()}.json").write_text(json.dumps(_scope(s)),encoding="utf-8")
def _git(s,events):
    def g(*args,root=ROOT):
        if args==("status","--porcelain"): return ""
        if args==("branch","--show-current"): return s["canonical_lineage"]["working_branch"]
        if args==("rev-parse","HEAD"): return H
        if args[:2]==("switch","-c"): events.append("create"); return ""
        if args==("switch",s["canonical_lineage"]["working_branch"]): events.append("rollback"); return ""
        if args[:2]==("branch","-D"): events.append("delete"); return ""
        raise AssertionError(args)
    return g
def test_decides_next_null_can_register_and_activate_atomically():
    s=base_plan(); assert s["next_package"] is None
    u=decided_transition(s,candidate=candidate(s),new_branch="test/dynamic",source_head=H,evidence=evidence()); old=s["active_package"]
    assert u["packages"][old]["status"]=="technical_pass"; assert u["packages"][old]["checkpoint"]==old
    assert u["packages"]["TEST-DYNAMIC"]["status"]=="active"; assert u["active_package"]=="TEST-DYNAMIC" and u["next_package"] is None
    assert u["canonical_lineage"]["current_package_base"]["sha"]==H
def test_dynamic_candidate_rejects_non_decider_bad_fields_and_dependencies():
    s=base_plan(); s["packages"][s["active_package"]]["decides_next"]=False
    with pytest.raises(ValueError,match="decide next"): validate_decided_candidate(s,candidate(s))
    s=base_plan(); bad=candidate(s); bad["unexpected"]=True
    with pytest.raises(ValueError,match="fields invalid"): validate_decided_candidate(s,bad)
    bad=candidate(s); bad["depends_on"]=["AUTH-002"]
    with pytest.raises(ValueError,match="directly depend"): validate_decided_candidate(s,bad)
    bad=candidate(s); bad["depends_on"]=[s["active_package"],"PROFILE-001"]
    with pytest.raises(ValueError,match="not ready"): validate_decided_candidate(s,bad)
def test_existing_package_must_be_compatible_planned_record():
    s=base_plan(); s["packages"]["TEST-PLANNED"]={"status":"planned","goal":"same","depends_on":[s["active_package"]],"decides_next":True}
    validate_decided_candidate(s,{"id":"TEST-PLANNED","goal":"same","depends_on":[s["active_package"]],"decides_next":True})
    with pytest.raises(ValueError,match="conflicts"): validate_decided_candidate(s,{"id":"TEST-PLANNED","goal":"different","depends_on":[s["active_package"]],"decides_next":True})
def test_waiver_never_overrides_wrong_head_or_failed_ci():
    runs=[{"name":"Foundation CI","headSha":H,"event":"pull_request","conclusion":"success","databaseId":1},{"name":"Review Source","headSha":H,"event":"pull_request","conclusion":"success","databaseId":2}]
    with pytest.raises(ValueError,match="Dependency Security"): validate_pr_evidence(pr={"headRefOid":H,"baseRefOid":B,"state":"OPEN"},runs=runs,merge_sha=C,merge_commit={"parents":[{"sha":B},{"sha":H}]},expected_head=H,pr_number=99,foundation_tree=C)
    with pytest.raises(ValueError,match="head"): validate_pr_evidence(pr={"headRefOid":"d"*40,"baseRefOid":B,"state":"OPEN"},runs=[],merge_sha=C,merge_commit={"parents":[{"sha":H}]},expected_head=H,pr_number=99,foundation_tree=C)
def test_failed_ci_stops_before_branch_creation(tmp_path,monkeypatch):
    import project_state as state
    s=base_plan(); _write_docs(tmp_path,s); calls=[]; monkeypatch.setattr(state,"git",_git(s,calls)); monkeypatch.setattr(state,"fetch_pr_evidence",lambda *a,**k:(_ for _ in ()).throw(ValueError("required workflow failed")))
    with pytest.raises(ValueError,match="workflow"): state.begin_decided_next(s,branch="test/dynamic",candidate=candidate(s),verified_pr=99,owner_waiver=True,independent_review_unavailable=True,owner_waiver_source=H,owner_waiver_reason="fixture",root=tmp_path)
    assert calls==[]
def test_failure_after_branch_creation_rolls_back_files_and_branch(tmp_path,monkeypatch):
    import project_state as state
    s=base_plan(); _write_docs(tmp_path,s); names=("PLAN.json","CURRENT.md","CHECKPOINTS.json"); originals={n:(tmp_path/"docs"/n).read_bytes() for n in names}; calls=[]
    monkeypatch.setattr(state,"git",_git(s,calls)); monkeypatch.setattr(state,"fetch_pr_evidence",lambda *a,**k:evidence()); monkeypatch.setattr(state,"fetch_review_evidence",lambda *a,**k:{"independent_review":"unavailable","owner_waiver":True,"owner_actor":"owner","owner_waiver_source":H,"owner_waiver_reason":"fixture"})
    def broken(updated,checkpoints=None,root=tmp_path):
        for n in names: (root/"docs"/n).write_text("partial",encoding="utf-8")
        raise OSError("disk failure")
    monkeypatch.setattr(state,"write_state",broken)
    with pytest.raises(OSError,match="disk failure"): state.begin_decided_next(s,branch="test/dynamic",candidate=candidate(s),verified_pr=99,owner_waiver=True,independent_review_unavailable=True,owner_waiver_source=H,owner_waiver_reason="fixture",root=tmp_path)
    for n,data in originals.items(): assert (tmp_path/"docs"/n).read_bytes()==data
    assert calls==["create","rollback","delete"]
def test_legacy_begin_next_still_works(tmp_path,monkeypatch):
    import project_state as state
    s=base_plan(); a=s["active_package"]; s["packages"]["TEST-LEGACY"]={"status":"planned_next","depends_on":[a],"decides_next":True}; s["next_package"]="TEST-LEGACY"; _write_docs(tmp_path,s); events=[]
    monkeypatch.setattr(state,"git",_git(s,events)); monkeypatch.setattr(state,"fetch_pr_evidence",lambda *a,**k:evidence()); monkeypatch.setattr(state,"fetch_review_evidence",lambda *a,**k:{"independent_review":"not_required","owner_waiver":False})
    u,_=state.begin_next(s,branch="test/legacy",activate="TEST-LEGACY",next_id=None,verified_pr=99,root=tmp_path)
    assert u["active_package"]=="TEST-LEGACY" and events==["create"]
def _minimal_scope(package_id,risk="medium",**extra):
    v={"package_id":package_id,"base":H,"scope_class":"tiny","risk":risk,"max_files":4,"allowed":["tools/*"],"sensitive_approved":["tools/*"]}; v.update(extra); return v
@pytest.mark.parametrize("mode",["missing","malformed","empty","wrong-package","wrong-risk","wrong-policy"])
def test_active_scope_fails_closed(mode,tmp_path):
    import project_state as state
    s=base_plan(); d=tmp_path/"tools/scopes"; d.mkdir(parents=True); p=d/f"{s['active_package'].lower()}.json"
    if mode=="malformed": p.write_text("{bad-json",encoding="utf-8")
    elif mode=="empty": p.write_text("{}",encoding="utf-8")
    elif mode=="wrong-package": p.write_text(json.dumps(_minimal_scope("OTHER-001")),encoding="utf-8")
    elif mode=="wrong-risk": p.write_text(json.dumps(_minimal_scope(s["active_package"],risk="critical")),encoding="utf-8")
    elif mode=="wrong-policy": p.write_text(json.dumps(_minimal_scope(s["active_package"],independent_review_required="yes")),encoding="utf-8")
    with pytest.raises(ValueError,match="scope"): state.active_scope(s,root=tmp_path)
@pytest.mark.parametrize("risk",["low","medium"])
def test_valid_low_medium_scope_remains_supported(risk,tmp_path):
    import project_state as state
    s=base_plan(); d=tmp_path/"tools/scopes"; d.mkdir(parents=True); expected=_minimal_scope(s["active_package"],risk=risk); (d/f"{s['active_package'].lower()}.json").write_text(json.dumps(expected),encoding="utf-8")
    assert state.active_scope(s,root=tmp_path)==expected
def test_missing_scope_blocks_before_branch_creation(tmp_path,monkeypatch):
    import project_state as state
    s=base_plan(); _write_docs(tmp_path,s,False); calls=[]; (tmp_path/"tools/scopes").mkdir(parents=True); monkeypatch.setattr(state,"git",_git(s,calls)); monkeypatch.setattr(state,"fetch_pr_evidence",lambda *a,**k:evidence()); monkeypatch.setattr(state,"fetch_review_evidence",lambda *a,**k:{"independent_review":"not_required","owner_waiver":False})
    with pytest.raises(ValueError,match="scope"): state.begin_decided_next(s,branch="test/dynamic",candidate=candidate(s),verified_pr=99,root=tmp_path)
    assert calls==[]
def _gate(monkeypatch,root,kind,review):
    import project_state as state
    s=base_plan(); events=[]; seen=[]
    if kind=="legacy": a=s["active_package"]; s["packages"]["TEST-MOCK"]={"status":"planned_next","depends_on":[a],"decides_next":True}; s["next_package"]="TEST-MOCK"
    _write_docs(root,s); monkeypatch.setattr(state,"git",_git(s,events)); monkeypatch.setattr(state,"fetch_pr_evidence",lambda *a,**k:evidence())
    def gate(*a,**k): seen.append(1); return review()
    monkeypatch.setattr(state,"fetch_review_evidence",gate)
    def call(**kw):
        if kind=="legacy": return state.begin_next(s,branch="test/mock",activate="TEST-MOCK",next_id=None,verified_pr=99,root=root,**kw)
        return state.begin_decided_next(s,branch="test/mock",candidate=candidate(s),verified_pr=99,root=root,**kw)
    return call,events,seen
@pytest.mark.parametrize("kind",["legacy","decided"])
@pytest.mark.parametrize("mode",["missing","blocked","waiver"])
def test_mocked_ci_still_enforces_review_and_waiver(kind,mode,tmp_path,monkeypatch):
    def review():
        if mode=="missing": raise ValueError("review required")
        if mode=="blocked": raise ValueError("changes requested")
        return {"independent_review":"unavailable","owner_waiver":True,"owner_waiver_source":H,"owner_waiver_reason":"fixture"}
    call,events,seen=_gate(monkeypatch,tmp_path,kind,review); kw={} if mode=="missing" else {"owner_waiver":True,"independent_review_unavailable":True,"owner_waiver_source":H,"owner_waiver_reason":"fixture"}
    if mode!="waiver":
        with pytest.raises(ValueError,match="review required|changes requested"): call(**kw)
        assert events==[]
    else: _,actual=call(**kw); assert actual["owner_waiver"] is True; assert events==["create"]
    assert seen==[1]
def test_active_scope_does_not_fall_back_outside_checkout(tmp_path):
    import project_state as state
    assert not (tmp_path/"tools").exists()
    with pytest.raises(ValueError,match="scope"): state.active_scope(base_plan(),root=tmp_path)
