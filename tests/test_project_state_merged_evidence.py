"""Historical checkpoint authentication for merged closeout transitions."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_state_evidence as common
from project_state_merged_evidence import authenticate_initial_checkpoint

WAIVER_GAP = "authenticated pre-introduction"


def _historical_case():
    source, base, tested = "1" * 40, "2" * 40, "3" * 40
    ids = {"Foundation CI": 11, "Dependency Security": 12, "Review Source": 13}
    checkpoint = {"type": "pr_merge_tree", "source_head": source, "verified_pr": 250,
                  "base_head": base, "tested_merge_tree": tested, "workflows": ids,
                  "independent_review": "unavailable", "owner_waiver": True,
                  "owner_actor": "owner", "owner_waiver_source": source,
                  "owner_waiver_reason": "Independent reviewer unavailable."}
    pr = {"headRefOid": source, "headRefName": "state/checkpoint", "baseRefOid": base}
    jobs = ((11, "verify"), (11, "bootstrap-windows"), (12, "npm-audit"), (13, "snapshot"))
    nodes = [{"__typename": "CheckRun", "name": name, "conclusion": "SUCCESS",
              "isRequired": True, "checkSuite": {"workflowRun": {"databaseId": run_id}}}
             for run_id, name in jobs]
    rollup = {"number": 250, **pr, "statusCheckRollup": {"state": "SUCCESS",
              "contexts": {"pageInfo": {"hasNextPage": False}, "nodes": nodes}}}
    runs = {"workflow_runs": [{"id": run_id, "name": name, "head_sha": source,
             "head_branch": "state/checkpoint", "event": "pull_request", "status": "completed",
             "conclusion": "success", "pull_requests": []}
             for name, run_id in ids.items()]}
    comment = {"id": 42, "user": {"login": "owner"}, "author_association": "OWNER",
               "created_at": "2026-09-29T15:39:17Z",
               "updated_at": "2026-09-29T15:39:17Z",
               "body": (f"FINAL EXACT-HEAD INDEPENDENT READ-ONLY CHALLENGE — APPROVE\n"
                        f"Source HEAD: `{source}`.\n- Foundation CI 11 SUCCESS\n"
                        "- Dependency Security 12 SUCCESS\n- Review Source 13 SUCCESS\n\n"
                        "Verdict: APPROVE.\nNo Chat P1 work started. Structured GitHub approval by a different account "
                        "remains unavailable; terminal checkpoint may use exact-SHA owner waiver as designed.")}
    return checkpoint, pr, rollup, runs, comment, tested


@pytest.mark.parametrize("mode,reason", [
    ("valid", None), ("wrong-pr", "source PR head/base"),
    ("wrong-run", "workflow run IDs"), ("wrong-tree", "tested merge tree mismatch"),
    ("foreign-rollup", "absent from PR rollup"),
    ("forged-waiver", WAIVER_GAP),
    ("after-pr-open", WAIVER_GAP),
    ("edited-after-introduction", WAIVER_GAP),
    ("equal-introduction", WAIVER_GAP),
    ("missing-update", WAIVER_GAP),
    ("extra-denial", WAIVER_GAP),
    ("quoted-waiver", WAIVER_GAP),
    ("wrong-owner-actor", "owner waiver identity mismatch"),
    ("review-before-introduction", None),
    ("review-after-introduction", "requires structured independent"),
])
def test_initial_checkpoint_requires_original_pr_ci_and_owner_action(monkeypatch, mode, reason):
    checkpoint, pr, rollup, runs, comment, tested = _historical_case()
    reviews = []
    if mode == "wrong-pr": pr["headRefOid"] = "9" * 40
    elif mode == "wrong-run": checkpoint["workflows"]["Foundation CI"] = 99
    elif mode == "wrong-tree": checkpoint["tested_merge_tree"] = "9" * 40
    elif mode == "foreign-rollup": rollup["statusCheckRollup"]["contexts"]["nodes"] = []
    elif mode == "forged-waiver": comment["user"]["login"] = "other"
    elif mode == "edited-after-introduction": comment["updated_at"] = "2026-09-29T15:45:00Z"
    elif mode == "equal-introduction": comment["created_at"] = "2026-09-29T15:41:57Z"
    elif mode == "missing-update": comment.pop("updated_at")
    elif mode == "extra-denial": comment["body"] = comment["body"].replace(
        "Verdict: APPROVE.", "I reject any owner waiver.\nVerdict: APPROVE.")
    elif mode == "quoted-waiver": comment["body"] = comment["body"].replace(
        "Structured GitHub approval", "> Structured GitHub approval")
    elif mode == "wrong-owner-actor": checkpoint["owner_actor"] = "other"
    if mode.startswith("review-"):
        checkpoint.update(independent_review="approved", owner_waiver=False,
                          independent_review_source=checkpoint["source_head"],
                          independent_review_actor="reviewer", independent_review_id=90)
        reviews = [{"id": 90, "state": "APPROVED", "commit_id": checkpoint["source_head"],
                    "submitted_at": ("2026-09-29T15:40:00Z" if mode == "review-before-introduction"
                                     else "2026-09-29T15:45:00Z"),
                    "user": {"login": "reviewer"}}]

    monkeypatch.setattr(common, "fetch_pr_rollup", lambda *a, **k: rollup)
    monkeypatch.setattr(common, "foundation_tested_sha", lambda *a, **k: tested)
    def fake_gh(args, root):
        path = " ".join(args)
        if args[:2] == ["pr", "view"]: return pr
        if "event=pull_request" in path: return [runs]
        if f"commits/{tested}" in path:
            return {"parents": [{"sha": checkpoint["base_head"]},
                                {"sha": checkpoint["source_head"]}]}
        if "/reviews?" in path: return [reviews]
        if "/comments?" in path: return [[comment]]
        raise AssertionError(args)
    monkeypatch.setattr(common, "gh_json", fake_gh)
    call = lambda: authenticate_initial_checkpoint(
        checkpoint, {"mergedAt": "2026-09-29T16:00:00Z", "createdAt":
                     "2026-09-29T15:38:00Z" if mode == "after-pr-open" else "2026-09-29T15:43:07Z"}, "owner/repo",
        introduced_at="2026-09-29T15:41:57Z")
    if reason:
        with pytest.raises(ValueError, match=reason): call()
    else:
        assert call() == {"checkpoint_pr": 250, "checkpoint_waiver_comment_id":
                          None if mode.startswith("review-") else 42}


def test_merged_closeout_requires_corresponding_checkpoint_and_review(monkeypatch):
    import project_state_evidence as evidence_module
    import project_state_merged_evidence as merged
    real_review = evidence_module.fetch_review_evidence
    package="PRE-P1-STABILIZATION-001"
    checkpoint,source_pr,source_rollup,source_runs,comment,source_tree=_historical_case()
    checkpoint_head=checkpoint["source_head"]
    head,base,merge,tree=(x*40 for x in "4567")
    scope={"risk":"medium","independent_review_required":True}
    source_records={}
    pr={"state":"MERGED","createdAt":"2026-09-29T15:43:07Z",
        "mergedAt":"2026-09-29T15:59:52Z","isDraft":False,
        "headRefOid":head,"headRefName":"state/closeout","baseRefOid":base,
        "mergeCommit":{"oid":merge}}
    def runs(names,sha,event,first):
        return {"workflow_runs":[{"id":n,"name":name,"head_sha":sha,"event":event,
            "status":"completed","conclusion":"success","run_attempt":1,
            "head_branch":"state/closeout","pull_requests":[{"number":252}]}
            for n,name in enumerate(names,first)]}
    pr_runs=runs(("Foundation CI","Dependency Security","Review Source"),head,"pull_request",1)
    push_runs=runs(("Foundation CI","Dependency Security"),merge,"push",4)
    seen=[]; closeout_comments=[]
    monkeypatch.setattr(evidence_module,"repo_slug",lambda root:"owner/repo")
    def fake_git(*args,root):
        if args[:2]==("merge-base","--is-ancestor"):
            if args[2:]!=(checkpoint_head,head): raise ValueError("not ancestor")
            return ""
        if args[:1]==("rev-list",): return f"{head} {checkpoint_head}"
        if args==("show","-s","--format=%cI",head): return "2026-09-29T15:41:57Z"
        if args==("show",f"{head}:docs/PLAN.json"):
            return json.dumps({"packages":{package:{"status":"complete","checkpoint":package}}})
        if args==("show",f"{head}:docs/CHECKPOINTS.json"):
            return json.dumps({"checkpoints":{package:checkpoint}})
        if args==("show",f"{checkpoint_head}:docs/PLAN.json"):
            return json.dumps({"packages":{package:{"status":"active"}}})
        if args==("show",f"{checkpoint_head}:docs/CHECKPOINTS.json"):
            return json.dumps({"checkpoints":source_records})
        raise AssertionError(args)
    monkeypatch.setattr(evidence_module,"git",fake_git)
    def fake_gh(args,root):
        path=" ".join(args)
        if args[:2]==["pr","view"]: return source_pr if args[2]=="250" else pr
        if "event=pull_request" in path:
            return [source_runs] if checkpoint_head in path else [pr_runs]
        if "event=push" in path: return [push_runs]
        if f"commits/{source_tree}" in path:
            return {"parents":[{"sha":checkpoint["base_head"]},{"sha":checkpoint_head}]}
        if f"commits/{merge}" in path or f"commits/{tree}" in path:
            return {"parents":[{"sha":base},{"sha":head}],
                    "commit":{"tree":{"sha":"f"*40}}}
        if "/reviews?" in path: return [[]]
        if "/issues/252/comments?" in path: return [closeout_comments]
        if "/comments?" in path: return [[comment]]
        if args==["api","user"]: return {"login":"owner"}
        raise AssertionError(args)
    monkeypatch.setattr(evidence_module,"gh_json",fake_gh)
    monkeypatch.setattr(evidence_module,"foundation_tested_sha",
        lambda run_id,slug,root: source_tree if run_id==11 else (tree if run_id==1 else merge))
    nodes=[{"__typename":"CheckRun","name":job,"conclusion":"SUCCESS",
            "isRequired":True,"checkSuite":{"workflowRun":{"databaseId":run_id}}}
           for run_id,job in ((1,"verify"),(1,"bootstrap-windows"),
                              (2,"npm-audit"),(3,"snapshot"))]
    rollup={"number":252,"headRefOid":head,"headRefName":"state/closeout",
            "baseRefOid":base,"statusCheckRollup":{"state":"SUCCESS",
            "contexts":{"pageInfo":{"hasNextPage":False},"nodes":nodes}}}
    monkeypatch.setattr(evidence_module,"fetch_pr_rollup",
        lambda number,*a,**k:source_rollup if number==250 else rollup)
    def review(scope_arg,pr_number,source_sha,**kwargs):
        assert scope_arg["independent_review_required"] is True
        seen.append((pr_number,source_sha,kwargs))
        return {"independent_review":"approved","independent_review_source":head,
                "independent_review_actor":"reviewer","owner_waiver":False}
    monkeypatch.setattr(evidence_module,"fetch_review_evidence",review)
    result=merged.fetch_merged_closeout_evidence(252,merge,package,checkpoint,scope)
    assert result["source_head"]==merge and result["checkpoint"]==package
    assert result["checkpoint_waiver_comment_id"]==42
    assert seen==[(252,head,{"root":evidence_module.ROOT})]
    scope["independent_review_required"]=False
    merged.fetch_merged_closeout_evidence(252,merge,package,checkpoint,scope)
    source_records[package]=dict(checkpoint)
    checkpoint["verified_pr"]=251
    with pytest.raises(ValueError,match="checkpoint.*rewrit|checkpoint.*changed"):
        merged.fetch_merged_closeout_evidence(252,merge,package,checkpoint,scope)
    checkpoint["verified_pr"]=250
    source_records.clear()
    monkeypatch.setattr(evidence_module,"fetch_review_evidence",
        lambda *a,**k: (_ for _ in ()).throw(ValueError("structured independent review missing")))
    with pytest.raises(ValueError,match="structured independent review missing"):
        merged.fetch_merged_closeout_evidence(252,merge,package,checkpoint,scope)
    closeout_comments.append({"id":99,"user":{"login":"owner"},"author_association":"OWNER",
        "created_at":"2026-09-29T15:55:00Z",
        "updated_at":"2026-09-29T15:55:00Z",
        "body":(f"Owner waiver for PR #252: APPROVE\nSource HEAD: {head}\n"
                "Independent review: unavailable\nReason: other account unavailable\n"
                "Foundation CI: 1 SUCCESS\nDependency Security: 2 SUCCESS\nReview Source: 3 SUCCESS")})
    monkeypatch.setattr(evidence_module,"fetch_review_evidence",real_review)
    accepted=merged.fetch_merged_closeout_evidence(252,merge,package,checkpoint,scope)
    assert accepted["closeout_waiver_comment_id"]==99
    assert accepted["owner_waiver_source"]==head
    checkpoint["source_head"]="9"*40
    with pytest.raises(ValueError,match="does not descend"):
        merged.fetch_merged_closeout_evidence(252,merge,package,checkpoint,scope)
