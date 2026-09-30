"""Small helpers for project-state transition I/O and scope evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path

from project_state_model import ROOT, load_checkpoints


def active_scope(plan: dict, *, root: Path) -> dict:
    package = plan["active_package"]
    path = root / "tools" / "scopes" / f"{package.lower()}.json"
    if not path.is_file():
        raise ValueError("active scope missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("active scope malformed") from exc
    if not isinstance(value, dict):
        raise ValueError("active scope invalid")
    risk, policy = value.get("risk"), value.get("independent_review_required")
    if (value.get("package_id") != package or risk not in {"low", "medium", "high"}
            or (policy is not None and type(policy) is not bool)
            or (risk == "high" and policy is not True)):
        raise ValueError("active scope invalid")
    return value


def state_paths(root: Path, *, checkpoints: bool = True) -> list[Path]:
    names = ["PLAN.json", "PACKAGES.json", "CURRENT.md"]
    if checkpoints:
        names.append("CHECKPOINTS.json")
    return [root / "docs" / name for name in names]


def assert_checkout_unchanged(source_head: str, current_branch: str, *, root: Path, git_fn) -> None:
    if (git_fn("rev-parse", "HEAD", root=root) != source_head
            or git_fn("branch", "--show-current", root=root) != current_branch
            or git_fn("status", "--porcelain", root=root)):
        raise ValueError("checkout changed during completed-source verification")


def completed_source_evidence(plan: dict, source_head: str, root: Path,
                              *, verified_pr: int | None = None) -> dict:
    active = plan["active_package"]
    if plan["packages"][active].get("status") != "complete":
        raise ValueError("completed-source evidence requires complete package")
    if plan["packages"][active].get("checkpoint") != active:
        raise ValueError("complete package checkpoint reference missing")
    checkpoint = load_checkpoints(root).get("checkpoints", {}).get(active)
    if not isinstance(checkpoint, dict):
        raise ValueError("complete package checkpoint evidence missing")
    if checkpoint.get("type") != "pr_merge_tree" or not isinstance(checkpoint.get("source_head"), str):
        raise ValueError("complete package accepted checkpoint evidence invalid")
    if source_head != checkpoint["source_head"]:
        if verified_pr is None:
            raise ValueError("verified merged closeout PR required for HEAD beyond checkpoint source")
        return fetch_merged_closeout_evidence(
            verified_pr, source_head, active, checkpoint, active_scope(plan, root=root), root=root,
        )
    return {
        "type": "completed_checkpoint",
        "source_head": source_head,
        "checkpoint": active,
        "checkpoint_source_head": checkpoint.get("source_head"),
    }


def write_transition(plan: dict, updated: dict, evidence: dict, *, branch: str,
                     current_branch: str, source_head: str, root: Path,
                     git_fn, write_state_fn, record_checkpoint: bool = True) -> None:
    checkpoints = json.loads(json.dumps(load_checkpoints(root)))
    if record_checkpoint:
        checkpoints.setdefault("checkpoints", {})[plan["active_package"]] = evidence
    paths = state_paths(root)
    originals = {path: path.read_bytes() if path.exists() else None for path in paths}
    git_fn("switch", "-c", branch, source_head, root=root)
    try:
        write_state_fn(updated, checkpoints, root=root)
    except Exception:
        for path, data in originals.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
        git_fn("switch", current_branch, root=root)
        git_fn("branch", "-D", branch, root=root)
        raise


def fetch_merged_closeout_evidence(pr_number: int, source_head: str, package: str,
                                   checkpoint: dict, scope: dict, *, root: Path = ROOT) -> dict:
    from project_state_evidence import (repo_slug, gh_json, git, _workflow_pages,
        latest_required_runs, foundation_tested_sha, validate_merged_closeout_evidence,
        fetch_review_evidence)
    slug = repo_slug(root)
    pr = gh_json(["pr", "view", str(pr_number), "--repo", slug,
                  "--json", "headRefOid,baseRefOid,isDraft,state,mergedAt,mergeCommit"], root=root)
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
    try:
        closeout_plan = json.loads(git("show", f"{head}:docs/PLAN.json", root=root))
        if not isinstance(closeout_plan, dict):
            raise ValueError("closeout PR plan invalid")
        if "packages" in closeout_plan:
            packages = closeout_plan
        elif closeout_plan.get("packages_ref") == "PACKAGES.json":
            packages = json.loads(git("show", f"{head}:docs/PACKAGES.json", root=root))
        else:
            raise ValueError("closeout PR package registry missing")
        checkpoints = json.loads(git("show", f"{head}:docs/CHECKPOINTS.json", root=root))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("closeout PR head lacks readable package/checkpoint state") from exc
    if not isinstance(packages, dict) or not isinstance(checkpoints, dict):
        raise ValueError("closeout PR package/checkpoint state invalid")
    items, records = packages.get("packages"), checkpoints.get("checkpoints")
    if not isinstance(items, dict) or not isinstance(records, dict):
        raise ValueError("closeout PR package/checkpoint registry invalid")
    item = items.get(package)
    if (not isinstance(item, dict) or item.get("status") != "complete"
            or item.get("checkpoint") != package
            or records.get(package) != checkpoint):
        raise ValueError("closeout PR head does not preserve the complete accepted checkpoint")
    pr_runs = _workflow_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/actions/runs?event=pull_request&head_sha={head}&per_page=100"], root=root))
    foundation = latest_required_runs(pr_runs, head, pr_number, allow_detached=True)["Foundation CI"]
    tested = foundation_tested_sha(int(foundation["databaseId"]), slug, root=root)
    push_runs = _workflow_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/actions/runs?event=push&head_sha={source_head}&per_page=100"], root=root))
    merge_commit = gh_json(["api", f"repos/{slug}/commits/{source_head}"], root=root)
    tested_commit = gh_json(["api", f"repos/{slug}/commits/{tested}"], root=root)
    evidence = validate_merged_closeout_evidence(
        pr=pr, pr_runs=pr_runs, push_runs=push_runs, merge_commit=merge_commit,
        tested_commit=tested_commit, tested_sha=tested, source_head=source_head,
        checkpoint_head=checkpoint_head, pr_number=pr_number)
    push_tree = foundation_tested_sha(evidence["push_workflows"]["Foundation CI"], slug, root=root)
    if push_tree != source_head:
        raise ValueError("merged HEAD Foundation CI did not test the exact merge commit")
    prior_waiver = (checkpoint.get("owner_waiver") is True
                    and checkpoint.get("independent_review") == "unavailable"
                    and checkpoint.get("source_head") == head
                    and checkpoint.get("owner_waiver_source") == head
                    and checkpoint.get("owner_actor") == slug.split("/", 1)[0])
    review_args = (dict(owner_waiver=True, independent_review_unavailable=True,
                        owner_waiver_source=head,
                        owner_waiver_reason=checkpoint.get("owner_waiver_reason"))
                   if prior_waiver else {})
    review = fetch_review_evidence(scope, pr_number, head, root=root, **review_args)
    evidence.update(review)
    evidence["checkpoint"] = package
    return evidence
