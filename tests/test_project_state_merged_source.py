"""A merged source PR can back an active package checkpoint only at exact lineage."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import project_state_evidence as evidence
import project_state_merged_source as merged
import project_state_provenance as provenance

HEAD, BASE, MERGE, TESTED, TREE = (letter * 40 for letter in "abcde")
RUN_IDS = {"Foundation CI": 11, "Dependency Security": 12, "Review Source": 13}


def fixture(monkeypatch):
    pr = {"state": "MERGED", "isDraft": False, "headRefOid": HEAD,
          "headRefName": "codex/p1-chat-history-paging-001", "baseRefOid": BASE,
          "mergeCommit": {"oid": MERGE}, "mergedAt": "2026-10-09T17:52:28Z"}
    runs = [{"name": name, "databaseId": number, "headSha": HEAD,
             "headBranch": pr["headRefName"], "event": "pull_request",
             "prNumbers": [], "status": "completed", "conclusion": "success",
             "runAttempt": 1, "updatedAt": "2026-10-09T17:50:00Z"}
            for name, number in RUN_IDS.items()]
    commits = {MERGE: {"parents": [{"sha": BASE}, {"sha": HEAD}],
                      "commit": {"tree": {"sha": TREE}}},
               TESTED: {"parents": [{"sha": BASE}, {"sha": HEAD}],
                        "commit": {"tree": {"sha": TREE}}}}
    nodes = [{"__typename": "CheckRun", "name": job, "isRequired": True,
              "conclusion": "SUCCESS", "checkSuite": {"workflowRun": {"databaseId": run}}}
             for run, job in ((11, "verify"), (11, "bootstrap-windows"),
                              (12, "npm-audit"), (13, "snapshot"))]
    rollup = {"number": 257, "headRefOid": HEAD, "headRefName": pr["headRefName"],
              "baseRefOid": BASE, "statusCheckRollup": {"state": "SUCCESS",
              "contexts": {"pageInfo": {"hasNextPage": False}, "nodes": nodes}}}
    main = [MERGE, "refs/heads/main"]
    monkeypatch.setattr(merged, "git", lambda *a, **k: "\t".join(main))
    monkeypatch.setattr(merged, "gh_json", lambda args, **k: commits[args[-1].split("/")[-1]])
    monkeypatch.setattr(merged, "foundation_tested_sha", lambda *a, **k: TESTED)
    monkeypatch.setattr(merged, "fetch_pr_rollup", lambda *a, **k: rollup)
    return pr, runs, commits, rollup, main


def verify(pr, runs):
    return merged.validate_merged_source_pr(257, HEAD, pr, runs, "owner/repo")


def test_exact_merged_source_pr(monkeypatch):
    pr, runs, *_ = fixture(monkeypatch)
    result = verify(pr, runs)
    assert result["source_head"] == HEAD
    assert result["merged_source_commit"] == MERGE
    assert result["workflows"] == RUN_IDS


@pytest.mark.parametrize("change,pattern", [
    ("later-main", "canonical main"), ("wrong-pr-head", "identity"),
    ("wrong-merge", "canonical main"), ("wrong-parent", "parents"),
    ("missing-ci", "Dependency Security"), ("wrong-branch", "head branch"),
    ("late-ci", "pre-source merge"), ("wrong-rollup", "rollup"),
    ("wrong-tree", "tree differs")])
def test_merged_source_fails_closed(monkeypatch, change, pattern):
    pr, runs, commits, rollup, main = fixture(monkeypatch)
    if change == "later-main": main[0] = "f" * 40
    elif change == "wrong-pr-head": pr["headRefOid"] = "f" * 40
    elif change == "wrong-merge": pr["mergeCommit"]["oid"] = "f" * 40
    elif change == "wrong-parent": commits[MERGE]["parents"][1]["sha"] = "f" * 40
    elif change == "missing-ci": runs.pop(1)
    elif change == "wrong-branch": runs[0]["headBranch"] = "other"
    elif change == "late-ci": runs[0]["updatedAt"] = "2026-10-09T17:53:00Z"
    elif change == "wrong-rollup": rollup["statusCheckRollup"]["contexts"]["nodes"].pop()
    elif change == "wrong-tree": commits[TESTED]["commit"]["tree"]["sha"] = "f" * 40
    with pytest.raises(ValueError, match=pattern):
        verify(pr, runs)


@pytest.mark.parametrize("change", ["wrong-pr", "wrong-head", "wrong-owner",
                                     "after-merge", "wrong-ci", "missing-approve"])
def test_merged_source_waiver_is_exact_and_premerge(monkeypatch, change):
    body = (f"Owner waiver for source checkpoint PR #257: APPROVE\n"
            f"Source HEAD: {HEAD}\nIndependent review: unavailable\nReason: reviewer unavailable\n"
            "Foundation CI: 11 SUCCESS\nDependency Security: 12 SUCCESS\n"
            "Review Source: 13 SUCCESS")
    comment = {"id": 42, "user": {"login": "owner"}, "author_association": "OWNER",
               "created_at": "2026-10-09T17:50:00Z",
               "updated_at": "2026-10-09T17:50:00Z", "body": body}
    if change == "wrong-pr": comment["body"] = body.replace("PR #257", "PR #258")
    elif change == "wrong-head": comment["body"] = body.replace(HEAD, "f" * 40)
    elif change == "wrong-owner": comment["user"]["login"] = "other"
    elif change == "after-merge": comment["created_at"] = "2026-10-09T17:53:00Z"
    elif change == "wrong-ci": comment["body"] = body.replace("12 SUCCESS", "99 SUCCESS")
    elif change == "missing-approve": comment["body"] = body.replace("APPROVE", "PASS")
    monkeypatch.setattr(evidence, "gh_json", lambda *a, **k: [[comment]])
    result = provenance._closeout_owner_waiver(257, HEAD, RUN_IDS,
        "2026-10-09T17:52:28Z", "owner/repo", source_checkpoint=True)
    assert result is None
