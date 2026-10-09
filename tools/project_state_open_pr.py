"""Validation of an open source PR merge ref."""
from __future__ import annotations
import re

def validate_pr_evidence(*, pr: dict, runs: list[dict], merge_sha: str,
                         merge_commit: dict, expected_head: str, pr_number: int,
                         foundation_tree: str) -> dict:
    from project_state_evidence import latest_required_runs, REQUIRED_WORKFLOWS
    if pr.get("headRefOid") != expected_head:
        raise ValueError(f"PR #{pr_number} head {pr.get('headRefOid')} != expected {expected_head}")
    if str(pr.get("state", "")).upper() != "OPEN":
        raise ValueError(f"PR #{pr_number} must still be open while used as checkpoint evidence")
    latest = latest_required_runs(runs, expected_head, pr_number)
    successful = {name: int(latest[name]["databaseId"]) for name in REQUIRED_WORKFLOWS}
    parents = [item.get("sha") for item in merge_commit.get("parents", [])]
    base_head = pr.get("baseRefOid")
    if expected_head not in parents or base_head not in parents:
        raise ValueError(f"PR merge tree {merge_sha} does not contain current source/base parents")
    if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        raise ValueError("merge tree SHA is invalid")
    if foundation_tree != merge_sha:
        raise ValueError(f"Foundation CI tested merge tree {foundation_tree}, current PR merge tree is {merge_sha}")
    return {"type": "pr_merge_tree", "source_head": expected_head, "verified_pr": pr_number,
            "base_head": base_head, "tested_merge_tree": merge_sha, "workflows": successful}

