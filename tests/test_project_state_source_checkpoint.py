"""Original checkpoint source provenance and chronology."""
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
             "conclusion": "success", "pull_requests": [], "run_attempt": 1,
             "updated_at": "2026-09-29T15:37:49Z"}
             for name, run_id in ids.items()]}
    comment = {"id": 42, "user": {"login": "owner"}, "author_association": "OWNER",
               "created_at": "2026-09-29T15:39:17Z",
               "updated_at": "2026-09-29T15:39:17Z",
               "body": (f"Owner waiver for source checkpoint PR #250: APPROVE\nSource HEAD: {source}\n"
                        "Independent review: unavailable\nReason: Independent reviewer unavailable.\n"
                        "Foundation CI: 11 SUCCESS\nDependency Security: 12 SUCCESS\nReview Source: 13 SUCCESS")}
    return checkpoint, pr, rollup, runs, comment, tested


@pytest.mark.parametrize("mode,reason", [
    ("valid", None), ("future-pr", None), ("wrong-pr", "source PR head/base"),
    ("waiver-wrong-pr", WAIVER_GAP), ("waiver-wrong-sha", WAIVER_GAP),
    ("waiver-wrong-ci", WAIVER_GAP),
    ("wrong-run", "workflow run IDs"), ("wrong-tree", "tested merge tree mismatch"),
    ("foreign-rollup", "absent from PR rollup"),
    ("forged-waiver", WAIVER_GAP),
    ("after-pr-open", WAIVER_GAP),
    ("edited-after-introduction", WAIVER_GAP),
    ("equal-introduction", WAIVER_GAP),
    ("missing-update", WAIVER_GAP),
    ("late-ci-rerun", "pre-checkpoint introduction"),
    ("equal-ci-update", "pre-checkpoint introduction"),
    ("missing-ci-time", "pre-checkpoint introduction"),
    ("missing-ci-attempt", "pre-checkpoint introduction"),
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
    elif mode == "future-pr":
        checkpoint["verified_pr"] = rollup["number"] = 253
        comment["body"] = comment["body"].replace("PR #250", "PR #253")
    elif mode == "waiver-wrong-pr": comment["body"] = comment["body"].replace("PR #250", "PR #251")
    elif mode == "waiver-wrong-sha":
        comment["body"] = comment["body"].replace(checkpoint["source_head"], "9" * 40)
    elif mode == "waiver-wrong-ci": comment["body"] = comment["body"].replace("Foundation CI: 11", "Foundation CI: 99")
    elif mode == "wrong-run": checkpoint["workflows"]["Foundation CI"] = 99
    elif mode == "wrong-tree": checkpoint["tested_merge_tree"] = "9" * 40
    elif mode == "foreign-rollup": rollup["statusCheckRollup"]["contexts"]["nodes"] = []
    elif mode == "forged-waiver": comment["user"]["login"] = "other"
    elif mode == "edited-after-introduction": comment["updated_at"] = "2026-09-29T15:45:00Z"
    elif mode == "equal-introduction": comment["created_at"] = "2026-09-29T15:41:57Z"
    elif mode == "missing-update": comment.pop("updated_at")
    elif mode == "late-ci-rerun": runs["workflow_runs"][0].update(
        run_attempt=2, updated_at="2026-09-29T15:42:00Z")
    elif mode == "equal-ci-update":
        runs["workflow_runs"][0]["updated_at"] = "2026-09-29T15:41:57Z"
    elif mode == "missing-ci-time": runs["workflow_runs"][0].pop("updated_at")
    elif mode == "missing-ci-attempt": runs["workflow_runs"][0].pop("run_attempt")
    elif mode == "extra-denial": comment["body"] = comment["body"].replace(
        "Reason:", "I reject any owner waiver.\nReason:")
    elif mode == "quoted-waiver": comment["body"] = comment["body"].replace(
        "Owner waiver for source checkpoint", "> Owner waiver for source checkpoint")
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
        assert call() == {"checkpoint_pr": checkpoint["verified_pr"], "checkpoint_waiver_comment_id":
                          None if mode.startswith("review-") else 42}
