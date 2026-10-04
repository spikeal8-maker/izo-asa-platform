"""Authenticate merged closeout PRs and checkpoint provenance."""
from __future__ import annotations

import re
from pathlib import Path

from project_state_model import ROOT
from project_state_checkpoint_provenance import authenticate_initial_checkpoint, checkpoint_introduction
from project_state_mechanical_closeout import mechanical_state_only_closeout, source_scope_at
from project_state_workflow import (_package_state_at, REQUIRED_PR_JOBS,
    validate_merged_closeout_evidence)
from project_state_provenance import _closeout_owner_waiver, legacy_pr252_review


def fetch_merged_closeout_evidence(pr_number: int, source_head: str, package: str,
                                   checkpoint: dict, scope: dict, *, root: Path = ROOT) -> dict:
    from project_state_evidence import (repo_slug, gh_json, git, _workflow_pages,
        latest_required_runs, foundation_tested_sha, fetch_pr_rollup,
        fetch_review_evidence)
    slug = repo_slug(root)
    pr = gh_json(["pr", "view", str(pr_number), "--repo", slug,
                  "--json", "headRefOid,headRefName,baseRefOid,isDraft,state,createdAt,mergedAt,mergeCommit"], root=root)
    if not isinstance(pr, dict):
        raise ValueError("closeout PR evidence missing")
    head = pr.get("headRefOid")
    checkpoint_head = checkpoint.get("source_head")
    if any(not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
           for sha in (head, checkpoint_head)):
        raise ValueError("closeout PR or checkpoint source SHA invalid")
    try:
        git("merge-base", "--is-ancestor", checkpoint_head, head, root=root)
    except ValueError as exc:
        raise ValueError("closeout PR head does not descend from accepted checkpoint source") from exc
    prior_item, prior_record, prior_exists = _package_state_at(
        checkpoint_head, package, root=root, git_fn=git)
    if prior_exists and prior_record != checkpoint:
        raise ValueError("accepted checkpoint was rewritten after its source commit")
    if not prior_exists and (not isinstance(prior_item, dict)
                             or prior_item.get("status") != "active"
                             or prior_item.get("checkpoint") is not None):
        raise ValueError("initial checkpoint creation requires active source package")
    introduced_at = (checkpoint_introduction(checkpoint_head, head, package, checkpoint,
                                               root=root, git_fn=git)
                     if not prior_exists else None)
    source_scope = (source_scope_at(checkpoint_head, package, root=root, git_fn=git)
                    if introduced_at is not None
                    and checkpoint.get("independent_review") == "not_required" else None)
    initial_provenance = (authenticate_initial_checkpoint(
        checkpoint, pr, slug, introduced_at=introduced_at, scope=source_scope, root=root)
        if introduced_at is not None else {})
    item, closeout_record, closeout_exists = _package_state_at(head, package, root=root, git_fn=git)
    if (not isinstance(item, dict) or item.get("status") != "complete"
            or item.get("checkpoint") != package
            or not closeout_exists or closeout_record != checkpoint):
        raise ValueError("closeout PR head does not preserve the complete accepted checkpoint")
    pr_runs = _workflow_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/actions/runs?event=pull_request&head_sha={head}&per_page=100"], root=root))
    foundation = latest_required_runs(pr_runs, head, pr_number, allow_detached=True,
                                      expected_branch=pr.get("headRefName"))["Foundation CI"]
    tested = foundation_tested_sha(int(foundation["databaseId"]), slug, root=root)
    push_runs = _workflow_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/actions/runs?event=push&head_sha={source_head}&per_page=100"], root=root))
    merge_commit = gh_json(["api", f"repos/{slug}/commits/{source_head}"], root=root)
    tested_commit = gh_json(["api", f"repos/{slug}/commits/{tested}"], root=root)
    rollup = fetch_pr_rollup(pr_number, slug, root=root)
    evidence = validate_merged_closeout_evidence(
        pr=pr, pr_runs=pr_runs, push_runs=push_runs, merge_commit=merge_commit,
        tested_commit=tested_commit, rollup=rollup, tested_sha=tested, source_head=source_head,
        checkpoint_head=checkpoint_head, pr_number=pr_number)
    push_tree = foundation_tested_sha(evidence["push_workflows"]["Foundation CI"], slug, root=root)
    if push_tree != source_head:
        raise ValueError("merged HEAD Foundation CI did not test the exact merge commit")
    if pr_number == 252:
        evidence.update(legacy_pr252_review(pr_number, head, source_head, pr,
                                              evidence["workflows"], slug, root=root))
    elif mechanical_state_only_closeout(
            pr_number, head, checkpoint_head, package, checkpoint, slug,
            root=root, git_fn=git, gh_fn=gh_json):
        evidence.update(independent_review="not_required", owner_waiver=False,
                        mechanical_state_only_closeout=True)
    else:
        waiver = _closeout_owner_waiver(pr_number, head, evidence["workflows"],
                                        pr.get("mergedAt"), slug, root=root)
        review_args = (dict(owner_waiver=True, independent_review_unavailable=True,
                            owner_waiver_source=head, owner_waiver_reason=waiver[0])
                       if waiver is not None else {})
        # Closeout review stays mandatory even if the later active scope is downgraded.
        review = fetch_review_evidence({"risk": "high", "independent_review_required": True},
                                        pr_number, head, root=root, approved_before=pr["mergedAt"],
                                        **review_args)
        evidence.update(review)
        if waiver is not None and review.get("owner_waiver") is True:
            evidence["closeout_waiver_comment_id"] = waiver[1]
    evidence.update(initial_provenance)
    evidence["checkpoint"] = package
    return evidence
