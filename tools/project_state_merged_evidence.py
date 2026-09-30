"""Authenticate merged closeout PRs and checkpoint provenance."""
from __future__ import annotations

import re
from pathlib import Path

from project_state_evidence import _time
from project_state_model import ROOT
from project_state_workflow import (_package_state_at, _push_workflows,
    _historical_waiver_body, _closeout_owner_waiver, REQUIRED_PR_JOBS,
    validate_merged_closeout_evidence)


def _checkpoint_introduction(source: str, head: str, package: str, checkpoint: dict,
                             *, root: Path, git_fn) -> str:
    history = git_fn("rev-list", "--ancestry-path", "--reverse", "--topo-order",
                     "--parents", f"{source}..{head}", root=root).splitlines()
    present = {source: False}
    first = []
    for line in history:
        sha, *parents = line.split()
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("closeout checkpoint introduction history invalid")
        item, record, exists = _package_state_at(sha, package, root=root, git_fn=git_fn)
        if exists and (record != checkpoint or not isinstance(item, dict)
                       or item.get("status") != "complete" or item.get("checkpoint") != package):
            raise ValueError("accepted checkpoint or complete status was rewritten in closeout history")
        if any(present.get(parent) is True for parent in parents):
            if not exists:
                raise ValueError("accepted checkpoint was removed in closeout history")
        elif exists:
            stamp = git_fn("show", "-s", "--format=%cI", sha, root=root).strip()
            first.append(_time(stamp, "checkpoint introduction"))
        present[sha] = exists
    if present.get(head) is not True or not first:
        raise ValueError("closeout checkpoint introduction cannot be established")
    # Equal-second events have no provable order: evidence must be strictly earlier.
    return min(first).isoformat()


def authenticate_initial_checkpoint(checkpoint: dict, closeout_pr: dict, slug: str,
                                    *, introduced_at: str, root: Path = ROOT) -> dict:
    from project_state_evidence import (gh_json, _workflow_pages, _flatten_pages,
        latest_required_runs, foundation_tested_sha, fetch_pr_rollup,
        validate_pr_rollup, REQUIRED_WORKFLOWS)
    from review_evidence import review_decision

    source, number = checkpoint.get("source_head"), checkpoint.get("verified_pr")
    if type(number) is not int or number < 1:
        raise ValueError("initial checkpoint source PR identity missing")
    pr = gh_json(["pr", "view", str(number), "--repo", slug,
                  "--json", "headRefOid,headRefName,baseRefOid"], root=root)
    if (not isinstance(pr, dict) or pr.get("headRefOid") != source
            or pr.get("baseRefOid") != checkpoint.get("base_head")
            or not pr.get("headRefName")):
        raise ValueError("initial checkpoint source PR head/base mismatch")
    runs = _workflow_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/actions/runs?event=pull_request&head_sha={source}&per_page=100"], root=root))
    latest = latest_required_runs(runs, source, number, allow_detached=True,
                                  expected_branch=pr["headRefName"])
    if not isinstance(checkpoint.get("workflows"), dict) or any(
            checkpoint["workflows"].get(name) != latest[name].get("databaseId")
            for name in REQUIRED_WORKFLOWS):
        raise ValueError("initial checkpoint required workflow run IDs mismatch")
    validate_pr_rollup(number, pr, latest, fetch_pr_rollup(number, slug, root=root),
                       REQUIRED_PR_JOBS)
    tested = foundation_tested_sha(int(latest["Foundation CI"]["databaseId"]), slug, root=root)
    if tested != checkpoint.get("tested_merge_tree"):
        raise ValueError("initial checkpoint tested merge tree mismatch")
    commit = gh_json(["api", f"repos/{slug}/commits/{tested}"], root=root)
    parents = [row.get("sha") for row in commit.get("parents", [])] if isinstance(commit, dict) else []
    if parents != [pr["baseRefOid"], source]:
        raise ValueError("initial checkpoint tested merge tree parents mismatch")

    introduced = _time(introduced_at, "checkpoint introduction")
    opened = _time(closeout_pr.get("createdAt"), "closeout PR creation")
    merged = _time(closeout_pr.get("mergedAt"), "closeout merge")
    if introduced >= merged or opened >= merged:
        raise ValueError("checkpoint introduction or PR creation does not precede closeout merge")
    # PR creation is server-attested; the author-controlled commit date only narrows this cutoff.
    cutoff = min(introduced, opened)
    reviews = _flatten_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/pulls/{number}/reviews?per_page=100"], root=root))
    reviews = [row for row in reviews if row.get("submitted_at")
               and _time(row["submitted_at"], "original PR review") < cutoff]
    owner = slug.split("/", 1)[0]
    comment_id = None
    if checkpoint.get("owner_waiver") is True:
        comments = _flatten_pages(gh_json(["api", "--paginate", "--slurp",
            f"repos/{slug}/issues/{number}/comments?per_page=100"], root=root))
        for row in comments:
            if ((row.get("user") or {}).get("login") == owner
                    and row.get("author_association") == "OWNER"
                    and row.get("created_at")
                    and row.get("updated_at")
                    and _time(row["created_at"], "original owner comment") < cutoff
                    and _time(row["updated_at"], "original owner comment update") < cutoff
                    and _historical_waiver_body(str(row.get("body") or ""), source, latest)):
                comment_id = row.get("id")
                break
        if type(comment_id) is not int:
            raise ValueError("initial checkpoint lacks authenticated pre-introduction exact-SHA owner waiver")
    decision = review_decision({"risk": "high"}, reviews, source, owner_login=owner,
        actor_login=owner if comment_id is not None else None,
        owner_waiver=comment_id is not None,
        independent_review_unavailable=comment_id is not None,
        owner_waiver_source=checkpoint.get("owner_waiver_source"),
        owner_waiver_reason=checkpoint.get("owner_waiver_reason"))
    if (decision.get("independent_review") != checkpoint.get("independent_review")
            or decision.get("owner_waiver") != checkpoint.get("owner_waiver")):
        raise ValueError("initial checkpoint review or waiver evidence mismatch")
    if comment_id is not None and any(decision.get(key) != checkpoint.get(key)
            for key in ("owner_actor", "owner_waiver_source", "owner_waiver_reason")):
        raise ValueError("initial checkpoint owner waiver identity mismatch")
    if comment_id is None and any(decision.get(key) != checkpoint.get(key)
            for key in ("independent_review_source", "independent_review_actor", "independent_review_id")):
        raise ValueError("initial checkpoint structured review identity mismatch")
    return {"checkpoint_pr": number, "checkpoint_waiver_comment_id": comment_id}


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
    introduced_at = (_checkpoint_introduction(checkpoint_head, head, package, checkpoint,
                                               root=root, git_fn=git)
                     if not prior_exists else None)
    initial_provenance = (authenticate_initial_checkpoint(
        checkpoint, pr, slug, introduced_at=introduced_at, root=root)
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
    waiver = _closeout_owner_waiver(pr_number, head, evidence["workflows"],
                                    pr.get("mergedAt"), slug, root=root)
    review_args = (dict(owner_waiver=True, independent_review_unavailable=True,
                        owner_waiver_source=head, owner_waiver_reason=waiver[0])
                   if waiver is not None else {})
    # Closeout review stays mandatory even if the later active scope is downgraded.
    review = fetch_review_evidence({"risk": "high", "independent_review_required": True},
                                   pr_number, head, root=root, **review_args)
    evidence.update(review)
    if waiver is not None and review.get("owner_waiver") is True:
        evidence["closeout_waiver_comment_id"] = waiver[1]
    evidence.update(initial_provenance)
    evidence["checkpoint"] = package
    return evidence
