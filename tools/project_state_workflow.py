"""Small helpers for project-state transition I/O and scope evidence."""
from __future__ import annotations

import json
from pathlib import Path

from project_state_model import load_checkpoints


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


def completed_source_evidence(plan: dict, source_head: str, root: Path) -> dict:
    active = plan["active_package"]
    if plan["packages"][active].get("status") != "complete":
        raise ValueError("completed-source evidence requires complete package")
    if plan["packages"][active].get("checkpoint") != active:
        raise ValueError("complete package checkpoint reference missing")
    checkpoint = load_checkpoints(root).get("checkpoints", {}).get(active)
    if not isinstance(checkpoint, dict):
        raise ValueError("complete package checkpoint evidence missing")
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
