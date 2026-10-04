"""Fail-closed proof for mechanical state-only closeout PRs."""
from __future__ import annotations

import json
from pathlib import Path

from project_state_model import render_current, serialize_checkpoints, validate_plan
from project_state_registry import serialize_packages, serialize_plan

MECHANICAL_CLOSEOUT_PATHS = frozenset({
    "docs/PLAN.json", "docs/PACKAGES.json", "docs/CURRENT.md", "docs/CHECKPOINTS.json",
})


def _json_at(sha: str, path: str, *, root: Path, git_fn) -> dict:
    value = json.loads(git_fn("show", f"{sha}:{path}", root=root))
    if not isinstance(value, dict):
        raise ValueError(f"mechanical closeout {path} must contain an object")
    return value


def source_scope_at(sha: str, package: str, *, root: Path, git_fn) -> dict:
    path = f"tools/scopes/{package.lower()}.json"
    try:
        value = json.loads(git_fn("show", f"{sha}:{path}", root=root))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("source checkpoint scope missing or malformed") from exc
    if not isinstance(value, dict):
        raise ValueError("source checkpoint scope invalid")
    risk, policy = value.get("risk"), value.get("independent_review_required")
    if (value.get("package_id") != package or risk not in {"low", "medium", "high"}
            or (policy is not None and type(policy) is not bool)
            or (risk == "high" and policy is not True)):
        raise ValueError("source checkpoint scope invalid")
    return value


def mechanical_state_only_closeout(pr_number: int, head: str, checkpoint_head: str,
                                   package: str, checkpoint: dict, slug: str, *,
                                   root: Path, git_fn, gh_fn) -> bool:
    """Prove a closeout is exactly the deterministic state transition, nothing else."""
    from project_state_evidence import _flatten_pages

    try:
        rows = _flatten_pages(gh_fn(["api", "--paginate", "--slurp",
            f"repos/{slug}/pulls/{pr_number}/files?per_page=100"], root=root))
    except (AssertionError, OSError, ValueError, json.JSONDecodeError):
        return False
    if not rows:
        return False
    changed = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "modified":
            return False
        filename = row.get("filename")
        if not isinstance(filename, str) or filename not in MECHANICAL_CLOSEOUT_PATHS:
            return False
        changed.add(filename)
    if not changed:
        return False

    source_plan = _json_at(checkpoint_head, "docs/PLAN.json", root=root, git_fn=git_fn)
    source_registry = _json_at(checkpoint_head, "docs/PACKAGES.json", root=root, git_fn=git_fn)
    source_checkpoints = _json_at(checkpoint_head, "docs/CHECKPOINTS.json", root=root, git_fn=git_fn)
    packages = source_registry.get("packages")
    if not isinstance(packages, dict):
        return False
    source_plan = json.loads(json.dumps(source_plan))
    source_plan["packages"] = packages
    try:
        validate_plan(source_plan)
    except ValueError:
        return False
    item = source_plan.get("packages", {}).get(package)
    if (not isinstance(item, dict) or item.get("status") != "active"
            or item.get("checkpoint") is not None or source_plan.get("next_package") is not None):
        return False

    expected = json.loads(json.dumps(source_plan))
    expected["packages"][package]["status"] = "complete"
    expected["packages"][package]["checkpoint"] = package
    expected["packages"][package].pop("evidence", None)
    try:
        validate_plan(expected)
    except ValueError:
        return False
    expected_checkpoints = json.loads(json.dumps(source_checkpoints))
    records = expected_checkpoints.setdefault("checkpoints", {})
    if package in records:
        return False
    records[package] = checkpoint

    expected_text = {
        "docs/PLAN.json": serialize_plan(expected),
        "docs/PACKAGES.json": serialize_packages(expected),
        "docs/CURRENT.md": render_current(expected),
        "docs/CHECKPOINTS.json": serialize_checkpoints(expected_checkpoints),
    }
    for filename, text in expected_text.items():
        try:
            actual = git_fn("show", f"{head}:{filename}", root=root)
        except ValueError:
            return False
        if actual.strip() != text.strip():
            return False
    return True
