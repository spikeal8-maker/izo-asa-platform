"""Freeze the current package without starting its successor."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from project_state import active_scope
from project_state_evidence import fetch_pr_evidence, fetch_review_evidence
from project_state_model import load_checkpoints, load_plan, validate_plan, write_state

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, root: Path = ROOT) -> str:
    result = subprocess.run(
        args, cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="strict", timeout=30,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"command failed: {' '.join(args)}")
    return result.stdout.strip()


def git(*args: str, root: Path = ROOT) -> str:
    return run(["git", *args], root=root)


def complete_transition(plan: dict, evidence: dict) -> dict:
    validate_plan(plan)
    active = plan["active_package"]
    item = plan["packages"][active]
    if item.get("status") != "active":
        raise ValueError("closeout requires an active package")
    if plan.get("next_package") is not None:
        raise ValueError("closeout requires next_package=null")
    source = str(evidence.get("source_head", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("closeout evidence requires exact source_head")
    result = json.loads(json.dumps(plan))
    result["packages"][active]["status"] = "complete"
    result["packages"][active]["checkpoint"] = active
    result["packages"][active].pop("evidence", None)
    validate_plan(result)
    return result


def complete_current(plan: dict, *, branch: str, verified_pr: int,
                     owner_waiver: bool = False,
                     independent_review_unavailable: bool = False,
                     owner_waiver_source: str | None = None,
                     owner_waiver_reason: str | None = None,
                     root: Path = ROOT) -> tuple[dict, dict]:
    validate_plan(plan)
    if git("status", "--porcelain", root=root):
        raise ValueError("closeout requires a clean checkout")
    current_branch = git("branch", "--show-current", root=root)
    if current_branch != plan["canonical_lineage"]["working_branch"]:
        raise ValueError("closeout must run from current working_branch")
    source_head = git("rev-parse", "HEAD", root=root)
    if branch == current_branch:
        raise ValueError("closeout requires a new state-transition branch")

    scope = active_scope(plan, root=root)
    evidence = fetch_pr_evidence(verified_pr, source_head, root=root)
    evidence.update(fetch_review_evidence(
        scope, verified_pr, source_head, root=root,
        owner_waiver=owner_waiver,
        independent_review_unavailable=independent_review_unavailable,
        owner_waiver_source=owner_waiver_source,
        owner_waiver_reason=owner_waiver_reason,
    ))
    updated = complete_transition(plan, evidence)
    checkpoints = json.loads(json.dumps(load_checkpoints(root)))
    checkpoints.setdefault("checkpoints", {})[plan["active_package"]] = evidence

    paths = [root / "docs" / name for name in ("PLAN.json", "CURRENT.md", "CHECKPOINTS.json")]
    originals = {path: path.read_bytes() if path.exists() else None for path in paths}
    git("switch", "-c", branch, source_head, root=root)
    try:
        write_state(updated, checkpoints, root=root)
    except Exception:
        for path, data in originals.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
        git("switch", current_branch, root=root)
        git("branch", "-D", branch, root=root)
        raise
    return updated, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--verified-pr", required=True, type=int)
    parser.add_argument("--owner-waiver", action="store_true")
    parser.add_argument("--independent-review-unavailable", action="store_true")
    parser.add_argument("--owner-waiver-source")
    parser.add_argument("--owner-waiver-reason")
    args = parser.parse_args()
    try:
        updated, evidence = complete_current(
            load_plan(), branch=args.branch, verified_pr=args.verified_pr,
            owner_waiver=args.owner_waiver,
            independent_review_unavailable=args.independent_review_unavailable,
            owner_waiver_source=args.owner_waiver_source,
            owner_waiver_reason=args.owner_waiver_reason,
        )
        active = updated["active_package"]
        print(f"STATE COMPLETE: package={active} status={updated['packages'][active]['status']}")
        print(f"EVIDENCE: source={evidence['source_head']} merge={evidence['tested_merge_tree']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"PROJECT STATE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
