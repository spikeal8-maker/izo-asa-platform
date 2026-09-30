"""Small helpers for project-state transition I/O and scope evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path

from project_state_evidence import _time
from project_state_model import load_checkpoints

REQUIRED_PR_JOBS = {"Foundation CI": {"verify", "bootstrap-windows"},
                    "Dependency Security": {"npm-audit"}, "Review Source": {"snapshot"}}


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
        from project_state_merged_evidence import fetch_merged_closeout_evidence
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


def _package_state_at(sha: str, package: str, *, root: Path, git_fn) -> tuple[dict | None, dict | None, bool]:
    try:
        plan = json.loads(git_fn("show", f"{sha}:docs/PLAN.json", root=root))
        if not isinstance(plan, dict):
            raise ValueError("plan invalid")
        if "packages" in plan:
            packages = plan
        elif plan.get("packages_ref") == "PACKAGES.json":
            packages = json.loads(git_fn("show", f"{sha}:docs/PACKAGES.json", root=root))
        else:
            raise ValueError("package registry missing")
        checkpoints = json.loads(git_fn("show", f"{sha}:docs/CHECKPOINTS.json", root=root))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"closeout lineage state at {sha} unreadable") from exc
    if not isinstance(packages, dict) or not isinstance(checkpoints, dict):
        raise ValueError(f"closeout lineage state at {sha} invalid")
    items, records = packages.get("packages"), checkpoints.get("checkpoints")
    if not isinstance(items, dict) or not isinstance(records, dict):
        raise ValueError(f"closeout lineage registry at {sha} invalid")
    return items.get(package), records.get(package), package in records


def _push_workflows(runs: list[dict], source_head: str) -> dict[str, int]:
    from project_state_evidence import _freshness
    result = {}
    for name in ("Foundation CI", "Dependency Security"):
        matching = [r for r in runs if r.get("name") == name and r.get("headSha") == source_head
                    and r.get("event") == "push"]
        if not matching:
            raise ValueError(f"merged HEAD {source_head} lacks push workflow {name}")
        latest = max(matching, key=_freshness)
        if (str(latest.get("status") or "").lower() != "completed"
                or str(latest.get("conclusion") or "").lower() != "success"):
            raise ValueError(f"latest merged HEAD push workflow {name} did not succeed")
        result[name] = int(latest["databaseId"])
    return result


def _historical_waiver_body(body: str, source: str, runs: dict) -> bool:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    permission = ("No Chat P1 work started. Structured GitHub approval by a different account remains unavailable; "
                  "terminal checkpoint may use exact-SHA owner waiver as designed.")
    prefix = ["FINAL EXACT-HEAD INDEPENDENT READ-ONLY CHALLENGE — APPROVE",
              f"Source HEAD: `{source}`."]
    checks = [f"- {name} {runs[name]['databaseId']} SUCCESS"
              for name in ("Foundation CI", "Dependency Security", "Review Source")]
    suffix = ["Verdict: APPROVE.", permission]
    historical = ["Fresh clone:", "- hygiene PASS",
                  "- tracked files 487 / tracked bytes 2,766,244",
                  "- >500 KB 0 / >1 MB 0 / >5 MB 0 / tracked junk 0",
                  "- focused hygiene + closeout + docs + boundaries + scope tests PASS",
                  "- scope 11/12; outside 0; unapproved sensitive 0",
                  "- terminal-state simulation: PRE-P1 status=complete, next=None",
                  "- terminal PLAN bytes=9,995 (<10,000 hard context budget)",
                  "- migrations changed 0", "- product runtime / Chat / providers changed 0"]
    return lines in (prefix + checks + suffix, prefix + historical + checks + suffix)


def _closeout_owner_waiver(pr_number: int, head: str, workflows: dict,
                           merged_at: str, slug: str, *, root: Path) -> tuple[str, int] | None:
    from project_state_evidence import gh_json, _flatten_pages

    cutoff = _time(merged_at, "closeout merge")
    comments = _flatten_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/issues/{pr_number}/comments?per_page=100"], root=root))
    owner = slug.split("/", 1)[0]
    for row in comments:
        if ((row.get("user") or {}).get("login") != owner
                or row.get("author_association") != "OWNER"):
            continue
        lines = [line.strip() for line in str(row.get("body") or "").splitlines()
                 if line.strip()]
        if len(lines) != 7 or not lines[3].startswith("Reason: "):
            continue
        reason = lines[3][len("Reason: "):]
        expected = [f"Owner waiver for PR #{pr_number}: APPROVE",
                    f"Source HEAD: {head}", "Independent review: unavailable",
                    f"Reason: {reason}",
                    *(f"{name}: {workflows[name]} SUCCESS" for name in
                      ("Foundation CI", "Dependency Security", "Review Source"))]
        if (lines != expected or not reason or len(reason) > 500
                or type(row.get("id")) is not int
                or not row.get("created_at") or not row.get("updated_at")):
            continue
        if max(_time(row[key], "closeout owner comment")
               for key in ("created_at", "updated_at")) < cutoff:
            return reason, row["id"]
    return None


def validate_merged_closeout_evidence(*, pr: dict, pr_runs: list[dict], push_runs: list[dict],
                                      merge_commit: dict, tested_commit: dict, rollup: dict,
                                      tested_sha: str, source_head: str,
                                      checkpoint_head: str, pr_number: int) -> dict:
    from project_state_evidence import (latest_required_runs, REQUIRED_WORKFLOWS,
        validate_pr_rollup)
    if not isinstance(pr, dict) or not isinstance(pr.get("mergeCommit"), dict):
        raise ValueError("closeout PR mergeCommit evidence missing")
    head, base = pr.get("headRefOid"), pr.get("baseRefOid")
    merge = pr["mergeCommit"].get("oid")
    if (str(pr.get("state", "")).upper() != "MERGED" or not pr.get("mergedAt")
            or pr.get("isDraft") is True):
        raise ValueError(f"closeout PR #{pr_number} is not an accepted merged PR")
    if any(not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
           for sha in (head, base, merge, checkpoint_head, source_head, tested_sha)):
        raise ValueError("closeout PR or checkpoint has invalid exact SHA")
    if merge != source_head:
        raise ValueError(f"HEAD {source_head} != closeout PR #{pr_number} mergeCommit {merge}")
    for label, commit in (("merge commit", merge_commit), ("tested PR merge tree", tested_commit)):
        if (not isinstance(commit, dict) or not isinstance(commit.get("parents"), list)
                or any(not isinstance(item, dict) for item in commit["parents"])):
            raise ValueError(f"closeout PR #{pr_number} {label} parent evidence missing")
        parents = [item.get("sha") for item in commit.get("parents", [])]
        if parents != [base, head]:
            raise ValueError(f"closeout PR #{pr_number} {label} does not match base/head parents")
    branch = pr.get("headRefName")
    pr_latest = latest_required_runs(pr_runs, head, pr_number,
                                     allow_detached=True, expected_branch=branch)
    validate_pr_rollup(pr_number, pr, pr_latest, rollup, REQUIRED_PR_JOBS)
    trees = [commit["commit"]["tree"]["sha"] if isinstance(commit.get("commit"), dict)
             and isinstance(commit["commit"].get("tree"), dict) else None
             for commit in (merge_commit, tested_commit)]
    if any(not isinstance(tree, str) or not re.fullmatch(r"[0-9a-f]{40}", tree)
           for tree in trees):
        raise ValueError("closeout PR merge tree evidence missing")
    if trees[0] != trees[1]:
        raise ValueError("tested PR merge tree differs from actual merge commit tree")
    push_latest = _push_workflows(push_runs, source_head)
    return {"type": "completed_merged_closeout", "source_head": source_head,
            "checkpoint_source_head": checkpoint_head, "verified_pr": pr_number,
            "closeout_head": head, "base_head": base, "tested_merge_tree": tested_sha,
            "workflows": {name: int(pr_latest[name]["databaseId"]) for name in REQUIRED_WORKFLOWS},
            "push_workflows": push_latest}
