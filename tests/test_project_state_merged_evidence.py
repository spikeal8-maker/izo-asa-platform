"""Merged closeout transition and checkpoint preservation."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from test_project_state_source_checkpoint import _historical_case
from test_project_state_closeout import _merged_inputs
from project_state_workflow import validate_merged_closeout_evidence
from project_state_provenance import legacy_pr252_review


LEGACY_HEAD = "afb7ce498f2aecdbbfaf10a652e5591f2c7d9ccd"
LEGACY_MERGE = "95f153acc3a7a3ce4163d2e59b6f3e44ba963906"
LEGACY_RUNS = {"Foundation CI": 36592337411, "Dependency Security": 36592337156,
               "Review Source": 36592337428}
LEGACY_BODY = """FINAL INDEPENDENT READ-ONLY REVIEW — APPROVE

Exact state HEAD: `afb7ce498f2aecdbbfaf10a652e5591f2c7d9ccd`.

Verified:
- permanent repository hygiene checker is deterministic/read-only/network-free and blocks tracked junk/private artifacts, unexpected archives/binaries, >1 MiB without exact metadata allowlist, >5 MiB by default, handwritten hard limits, and >80% near-limit growth
- broad allowlist: none
- canonical-mode `python tools/project_state.py verify`: PASS
- `python tools/check_docs.py`: PASS
- repository hygiene: PASS
- state-only scope: 4/4; outside scope 0; unapproved sensitive 0
- PLAN size: 9,995 bytes
- PRE-P1-STABILIZATION-001: complete + checkpoint
- checkpoint source: `9bed77548d07f113bc806b1e5016076edb2646e1`
- next_package: NONE
- Chat P1 started: NO
- migrations/product runtime/providers/Chat runtime changed by state delta: NO
- Foundation CI `36592337411`: SUCCESS
- Dependency Security `36592337156`: SUCCESS
- Review Source `36592337428`: SUCCESS

Verdict: APPROVE. No findings."""


def _legacy_review_case(monkeypatch):
    import project_state_evidence as evidence_module
    slug = "spikeal8-maker/izo-asa-platform"
    pr = {"headRefOid": LEGACY_HEAD, "mergeCommit": {"oid": LEGACY_MERGE},
          "mergedAt": "2026-09-29T15:59:52Z"}
    comment = {"id": 5893861963, "issue_url": f"https://api.github.com/repos/{slug}/issues/252",
               "user": {"login": "spikeal8-maker"}, "author_association": "OWNER",
               "created_at": "2026-09-29T15:59:25Z",
               "updated_at": "2026-09-29T15:59:25Z", "body": LEGACY_BODY}
    monkeypatch.setattr(evidence_module, "gh_json", lambda *a, **k: comment)
    monkeypatch.setattr(evidence_module, "git", lambda *a, **k:
        f"{LEGACY_MERGE}\trefs/heads/main")
    return [252, LEGACY_HEAD, LEGACY_MERGE, pr, dict(LEGACY_RUNS), slug], comment


def test_exact_legacy_pr252_review_is_not_a_waiver(monkeypatch):
    args, _ = _legacy_review_case(monkeypatch)
    result = legacy_pr252_review(*args)
    assert result == {"independent_review": "legacy_owner_authenticated",
                      "independent_review_source": LEGACY_HEAD,
                      "legacy_closeout_comment_id": 5893861963,
                      "owner_waiver": False}


def test_legacy_pr252_survives_verified_future_main_descendant(monkeypatch):
    import project_state_evidence as evidence_module
    args, comment = _legacy_review_case(monkeypatch)
    future = "c" * 40
    monkeypatch.setattr(evidence_module, "git", lambda *a, **k:
        f"{future}\trefs/heads/main")
    def get_json(command, **kwargs):
        if "/compare/" in command[-1]:
            return {"status": "ahead", "base_commit": {"sha": LEGACY_MERGE},
                    "head_commit": {"sha": future}}
        return comment
    monkeypatch.setattr(evidence_module, "gh_json", get_json)
    assert legacy_pr252_review(*args)["legacy_closeout_comment_id"] == 5893861963


@pytest.mark.parametrize("mode", ["wrong-pr", "wrong-head", "wrong-merge",
    "wrong-comment-id", "after-merge", "wrong-owner", "missing-approve",
    "wrong-ci-ids", "wrong-body-ci-id", "wrong-main", "wrong-issue",
    "edited-after-merge"])
def test_legacy_pr252_rejects_any_identity_or_evidence_mismatch(monkeypatch, mode):
    import project_state_evidence as evidence_module
    args, comment = _legacy_review_case(monkeypatch)
    if mode == "wrong-pr": args[0] = 251
    elif mode == "wrong-head": args[1] = "a" * 40
    elif mode == "wrong-merge": args[2] = "b" * 40
    elif mode == "wrong-comment-id": comment["id"] = 1
    elif mode == "after-merge": comment["created_at"] = "2026-09-29T16:00:00Z"
    elif mode == "wrong-owner": comment["user"]["login"] = "other"
    elif mode == "missing-approve": comment["body"] = LEGACY_BODY.replace("APPROVE", "PASS")
    elif mode == "wrong-ci-ids": args[4]["Foundation CI"] += 1
    elif mode == "wrong-body-ci-id":
        comment["body"] = LEGACY_BODY.replace("36592337411", "36592337412")
    elif mode == "wrong-issue": comment["issue_url"] += "1"
    elif mode == "edited-after-merge": comment["updated_at"] = "2026-09-29T16:00:00Z"
    else:
        monkeypatch.setattr(evidence_module, "git", lambda *a, **k:
            f"{'c' * 40}\trefs/heads/main")
    with pytest.raises(ValueError, match="PR #252 legacy"):
        legacy_pr252_review(*args)


@pytest.mark.parametrize("mode", ["late-rerun", "equal-merge", "missing-update", "missing-attempt"])
def test_closeout_pr_ci_attempt_must_finish_before_merge(mode):
    fixture = _merged_inputs()
    run = fixture["pr_runs"][0]
    if mode == "late-rerun":
        run.update(runAttempt=2, updatedAt="2026-09-29T16:01:00Z")
    elif mode == "equal-merge":
        run["updatedAt"] = fixture["pr"]["mergedAt"]
    elif mode == "missing-update":
        run.pop("updatedAt")
    else:
        run.pop("runAttempt")
    with pytest.raises(ValueError, match="pre-closeout merge attempt"):
        validate_merged_closeout_evidence(**fixture)


def test_other_merged_closeout_requires_corresponding_checkpoint_and_review(monkeypatch):
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
            "updated_at":"2026-09-29T15:58:44Z",
            "head_branch":"state/closeout","pull_requests":[{"number":255}]}
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
        if "/issues/255/comments?" in path: return [closeout_comments]
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
    rollup={"number":255,"headRefOid":head,"headRefName":"state/closeout",
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
    result=merged.fetch_merged_closeout_evidence(255,merge,package,checkpoint,scope)
    assert result["source_head"]==merge and result["checkpoint"]==package
    assert result["checkpoint_waiver_comment_id"]==42
    assert seen==[(255,head,{"root":evidence_module.ROOT,"approved_before":pr["mergedAt"]})]
    scope["independent_review_required"]=False
    merged.fetch_merged_closeout_evidence(255,merge,package,checkpoint,scope)
    source_records[package]=dict(checkpoint)
    checkpoint["verified_pr"]=251
    with pytest.raises(ValueError,match="checkpoint.*rewrit|checkpoint.*changed"):
        merged.fetch_merged_closeout_evidence(255,merge,package,checkpoint,scope)
    checkpoint["verified_pr"]=250
    source_records.clear()
    monkeypatch.setattr(evidence_module,"fetch_review_evidence",
        lambda *a,**k: (_ for _ in ()).throw(ValueError("structured independent review missing")))
    with pytest.raises(ValueError,match="structured independent review missing"):
        merged.fetch_merged_closeout_evidence(255,merge,package,checkpoint,scope)
    closeout_comments.append({"id":99,"user":{"login":"owner"},"author_association":"OWNER",
        "created_at":"2026-09-29T15:55:00Z",
        "updated_at":"2026-09-29T15:55:00Z",
        "body":(f"Owner waiver for PR #255: APPROVE\nSource HEAD: {head}\n"
                "Independent review: unavailable\nReason: other account unavailable\n"
                "Foundation CI: 1 SUCCESS\nDependency Security: 2 SUCCESS\nReview Source: 3 SUCCESS")})
    monkeypatch.setattr(evidence_module,"fetch_review_evidence",real_review)
    accepted=merged.fetch_merged_closeout_evidence(255,merge,package,checkpoint,scope)
    assert accepted["closeout_waiver_comment_id"]==99
    assert accepted["owner_waiver_source"]==head
    checkpoint["source_head"]="9"*40
    with pytest.raises(ValueError,match="does not descend"):
        merged.fetch_merged_closeout_evidence(255,merge,package,checkpoint,scope)
