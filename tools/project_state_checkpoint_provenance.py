"""Authenticate the source checkpoint introduced by a closeout PR."""
from __future__ import annotations

import re
from pathlib import Path

from project_state_model import ROOT
from project_state_provenance import _source_waiver_body, _time, require_pr_runs_before
from project_state_workflow import _package_state_at, REQUIRED_PR_JOBS


def checkpoint_introduction(source: str, head: str, package: str, checkpoint: dict,
                            *, root: Path, git_fn) -> str:
    history = git_fn(
        "rev-list", "--ancestry-path", "--reverse", "--topo-order",
        "--parents", f"{source}..{head}", root=root,
    ).splitlines()
    present = {source: False}
    first = []
    for line in history:
        sha, *parents = line.split()
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("closeout checkpoint introduction history invalid")
        item, record, exists = _package_state_at(sha, package, root=root, git_fn=git_fn)
        if exists and (
            record != checkpoint
            or not isinstance(item, dict)
            or item.get("status") != "complete"
            or item.get("checkpoint") != package
        ):
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
    return min(first).isoformat()


def authenticate_initial_checkpoint(
    checkpoint: dict,
    closeout_pr: dict,
    slug: str,
    *,
    introduced_at: str,
    scope: dict | None = None,
    root: Path = ROOT,
) -> dict:
    from project_state_evidence import (
        REQUIRED_WORKFLOWS,
        _flatten_pages,
        _workflow_pages,
        fetch_pr_rollup,
        foundation_tested_sha,
        gh_json,
        latest_required_runs,
        validate_pr_rollup,
    )
    from review_evidence import review_decision

    source, number = checkpoint.get("source_head"), checkpoint.get("verified_pr")
    if type(number) is not int or number < 1:
        raise ValueError("initial checkpoint source PR identity missing")
    pr = gh_json(
        ["pr", "view", str(number), "--repo", slug,
         "--json", "headRefOid,headRefName,baseRefOid"],
        root=root,
    )
    if (
        not isinstance(pr, dict)
        or pr.get("headRefOid") != source
        or pr.get("baseRefOid") != checkpoint.get("base_head")
        or not pr.get("headRefName")
    ):
        raise ValueError("initial checkpoint source PR head/base mismatch")

    runs = _workflow_pages(gh_json(
        ["api", "--paginate", "--slurp",
         f"repos/{slug}/actions/runs?event=pull_request&head_sha={source}&per_page=100"],
        root=root,
    ))
    latest = latest_required_runs(
        runs, source, number, allow_detached=True, expected_branch=pr["headRefName"],
    )
    if not isinstance(checkpoint.get("workflows"), dict) or any(
        checkpoint["workflows"].get(name) != latest[name].get("databaseId")
        for name in REQUIRED_WORKFLOWS
    ):
        raise ValueError("initial checkpoint required workflow run IDs mismatch")
    validate_pr_rollup(
        number, pr, latest, fetch_pr_rollup(number, slug, root=root), REQUIRED_PR_JOBS,
    )

    tested = foundation_tested_sha(
        int(latest["Foundation CI"]["databaseId"]), slug, root=root,
    )
    if tested != checkpoint.get("tested_merge_tree"):
        raise ValueError("initial checkpoint tested merge tree mismatch")
    commit = gh_json(["api", f"repos/{slug}/commits/{tested}"], root=root)
    parents = [
        row.get("sha") for row in commit.get("parents", [])
    ] if isinstance(commit, dict) else []
    if parents != [pr["baseRefOid"], source]:
        raise ValueError("initial checkpoint tested merge tree parents mismatch")

    introduced = _time(introduced_at, "checkpoint introduction")
    opened = _time(closeout_pr.get("createdAt"), "closeout PR creation")
    merged = _time(closeout_pr.get("mergedAt"), "closeout merge")
    if introduced >= merged or opened >= merged:
        raise ValueError("checkpoint introduction or PR creation does not precede closeout merge")
    cutoff = min(introduced, opened)
    require_pr_runs_before(latest, cutoff.isoformat(), "checkpoint introduction")

    reviews = _flatten_pages(gh_json(
        ["api", "--paginate", "--slurp", f"repos/{slug}/pulls/{number}/reviews?per_page=100"],
        root=root,
    ))
    reviews = [
        row for row in reviews
        if row.get("submitted_at")
        and _time(row["submitted_at"], "original PR review") < cutoff
    ]
    owner = slug.split("/", 1)[0]
    comment_id = None
    if checkpoint.get("owner_waiver") is True:
        comments = _flatten_pages(gh_json(
            ["api", "--paginate", "--slurp", f"repos/{slug}/issues/{number}/comments?per_page=100"],
            root=root,
        ))
        for row in comments:
            body = str(row.get("body") or "")
            if (
                (row.get("user") or {}).get("login") == owner
                and row.get("author_association") == "OWNER"
                and row.get("created_at")
                and row.get("updated_at")
                and _time(row["created_at"], "original owner comment") < cutoff
                and _time(row["updated_at"], "original owner comment update") < cutoff
                and _source_waiver_body(
                    body, number, source, latest, checkpoint.get("owner_waiver_reason")
                )
            ):
                comment_id = row.get("id")
                break
        if type(comment_id) is not int:
            raise ValueError("initial checkpoint lacks authenticated pre-introduction exact-SHA owner waiver")

    decision = review_decision(
        scope or {"risk": "high"},
        reviews,
        source,
        owner_login=owner,
        actor_login=owner if comment_id is not None else None,
        owner_waiver=comment_id is not None,
        independent_review_unavailable=comment_id is not None,
        owner_waiver_source=checkpoint.get("owner_waiver_source"),
        owner_waiver_reason=checkpoint.get("owner_waiver_reason"),
    )
    if (
        decision.get("independent_review") != checkpoint.get("independent_review")
        or decision.get("owner_waiver") != checkpoint.get("owner_waiver")
    ):
        raise ValueError("initial checkpoint review or waiver evidence mismatch")
    if comment_id is not None and any(
        decision.get(key) != checkpoint.get(key)
        for key in ("owner_actor", "owner_waiver_source", "owner_waiver_reason")
    ):
        raise ValueError("initial checkpoint owner waiver identity mismatch")
    if comment_id is None and any(
        decision.get(key) != checkpoint.get(key)
        for key in ("independent_review_source", "independent_review_actor", "independent_review_id")
    ):
        raise ValueError("initial checkpoint structured review identity mismatch")
    return {"checkpoint_pr": number, "checkpoint_waiver_comment_id": comment_id}
