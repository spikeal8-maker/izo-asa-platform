"""Exact merged source PR evidence for an active package checkpoint."""
from __future__ import annotations
import re
from pathlib import Path
from project_state_model import ROOT
from project_state_evidence import (git, gh_json, latest_required_runs, validate_pr_rollup, fetch_pr_rollup, foundation_tested_sha, REQUIRED_WORKFLOWS)

def validate_merged_source_pr(pr_number: int, expected_head: str, pr: dict,
                              runs: list[dict], slug: str, *, root: Path = ROOT) -> dict:
    """Accept a merged source PR only while canonical main is its exact merge commit."""
    from project_state_provenance import require_pr_runs_before
    from project_state_workflow import REQUIRED_PR_JOBS

    head, base = pr.get("headRefOid"), pr.get("baseRefOid")
    merge = (pr.get("mergeCommit") or {}).get("oid")
    if (head != expected_head or pr.get("isDraft") is True or not pr.get("mergedAt")
            or any(not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
                   for sha in (head, base, merge))):
        raise ValueError(f"merged source PR #{pr_number} head/base/merge identity missing or mismatched")
    main = git("ls-remote", "origin", "refs/heads/main", root=root).split()
    if main != [merge, "refs/heads/main"]:
        raise ValueError(f"canonical main must equal merged source PR #{pr_number} merge commit {merge}")
    commit = gh_json(["api", f"repos/{slug}/commits/{merge}"], root=root)
    if [row.get("sha") for row in commit.get("parents", [])] != [base, head]:
        raise ValueError(f"merged source PR #{pr_number} merge parents do not match base/head")
    latest = latest_required_runs(runs, head, pr_number, allow_detached=True,
                                  expected_branch=pr.get("headRefName"))
    require_pr_runs_before(latest, pr["mergedAt"], "source merge")
    validate_pr_rollup(pr_number, pr, latest, fetch_pr_rollup(pr_number, slug, root=root),
                       REQUIRED_PR_JOBS)
    tested = foundation_tested_sha(int(latest["Foundation CI"]["databaseId"]), slug, root=root)
    tested_commit = gh_json(["api", f"repos/{slug}/commits/{tested}"], root=root)
    if [row.get("sha") for row in tested_commit.get("parents", [])] != [base, head]:
        raise ValueError("Foundation CI tested merge tree parents do not match merged source PR")
    trees = [row.get("commit", {}).get("tree", {}).get("sha")
             for row in (commit, tested_commit)]
    if (any(not isinstance(tree, str) or not re.fullmatch(r"[0-9a-f]{40}", tree)
            for tree in trees) or trees[0] != trees[1]):
        raise ValueError("Foundation CI tested merge tree differs from actual source merge commit tree")
    return {"type": "pr_merge_tree", "source_head": head, "verified_pr": pr_number,
            "base_head": base, "tested_merge_tree": tested,
            "merged_source_commit": merge, "merged_at": pr["mergedAt"],
            "workflows": {name: int(latest[name]["databaseId"]) for name in REQUIRED_WORKFLOWS}}
