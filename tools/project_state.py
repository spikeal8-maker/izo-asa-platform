"""Inspect and transition IZO ASA project state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from project_state_model import (CHECKPOINTS_PATH, NEXT_PACKAGE_SOURCE_STATUSES, PACKAGES_PATH,
    PLAN_PATH, READY_DEPENDENCY_STATUSES, RECONCILIATION_GAPS, ROOT, dependency_problems,
    load_checkpoints, load_plan, reconcile_continuation_transition, render_current,
    serialize_checkpoints, serialize_packages, serialize_plan, transition, validate_plan,
    validate_ref, write_state)
from project_state_decision import decided_transition, validate_decided_candidate
from project_state_evidence import fetch_pr_evidence, fetch_review_evidence, validate_pr_evidence
from project_state_workflow import (
    active_scope, completed_source_evidence, state_paths, write_transition,
)
def run(args: list[str], *, root: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="strict", timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"command failed: {' '.join(args)}")
    return result.stdout.strip()
def git(*args: str, root: Path = ROOT) -> str:
    return run(["git", *args], root=root)

def show_package(plan: dict, package_id: str) -> dict:
    packages = plan["packages"]
    item = packages.get(package_id)
    if item is None:
        raise ValueError(f"unknown package {package_id}")
    dependencies = {
        dep: {
            key: value for key, value in packages[dep].items()
            if key in {"status", "checkpoint", "goal"}
        }
        for dep in item.get("depends_on", [])
    }
    return {"package_id": package_id, "package": item, "dependencies": dependencies}


def verify_checkout(plan: dict, root: Path = ROOT) -> list[str]:
    validate_plan(plan)
    problems: list[str] = []
    lineage = plan["canonical_lineage"]
    branch = git("branch", "--show-current", root=root)
    head = git("rev-parse", "HEAD", root=root)
    base = lineage["current_package_base"]
    try:
        git("merge-base", "--is-ancestor", base["sha"], head, root=root)
    except ValueError:
        problems.append(f"HEAD {head} is not descended from current_package_base {base['sha']}")
    if branch != lineage["working_branch"]:
        problems.append(f"checkout branch {branch} != PLAN working_branch {lineage['working_branch']}")
    return problems
def _transition_evidence(plan: dict, pr: int, source_head: str, review: dict, root: Path) -> dict:
    scope = active_scope(plan, root=root)
    evidence = fetch_pr_evidence(pr, source_head, root=root)
    evidence.update(fetch_review_evidence(scope, pr, source_head, root=root, **review))
    return evidence


def begin_next(plan: dict, *, branch: str, activate: str, next_id: str | None,
               verified_pr: int, owner_waiver: bool = False,
               independent_review_unavailable: bool = False,
               owner_waiver_source: str | None = None,
               owner_waiver_reason: str | None = None, root: Path = ROOT) -> tuple[dict, dict]:
    validate_plan(plan)
    if git("status", "--porcelain", root=root):
        raise ValueError("begin-next requires a clean checkout")
    current_branch = git("branch", "--show-current", root=root)
    if current_branch != plan["canonical_lineage"]["working_branch"]:
        raise ValueError("begin-next must run from current working_branch")
    source_head = git("rev-parse", "HEAD", root=root)
    if branch == current_branch:
        raise ValueError("next package requires a new branch")
    review = dict(owner_waiver=owner_waiver,
                  independent_review_unavailable=independent_review_unavailable,
                  owner_waiver_source=owner_waiver_source, owner_waiver_reason=owner_waiver_reason)
    evidence = _transition_evidence(plan, verified_pr, source_head, review, root)
    updated = transition(plan, activate=activate, next_id=next_id, new_branch=branch,
                         source_head=source_head, evidence=evidence)
    write_transition(
        plan, updated, evidence, branch=branch, current_branch=current_branch,
        source_head=source_head, root=root, git_fn=git, write_state_fn=write_state,
    )
    return updated, evidence
def begin_decided_next(plan: dict, *, branch: str, candidate: dict, verified_pr: int | None,
                       owner_waiver: bool = False,
                       independent_review_unavailable: bool = False,
                       owner_waiver_source: str | None = None,
                       owner_waiver_reason: str | None = None,
                       root: Path = ROOT) -> tuple[dict, dict]:
    validate_plan(plan)
    if git("status", "--porcelain", root=root):
        raise ValueError("begin-decided-next requires a clean checkout")
    current_branch = git("branch", "--show-current", root=root)
    if current_branch != plan["canonical_lineage"]["working_branch"]:
        raise ValueError("begin-decided-next must run from current working_branch")
    source_head = git("rev-parse", "HEAD", root=root)
    if branch == current_branch:
        raise ValueError("next package requires a new branch")
    validate_decided_candidate(plan, candidate)
    finishing_status = plan["packages"][plan["active_package"]]["status"]
    if finishing_status == "complete":
        evidence = completed_source_evidence(plan, source_head, root)
        record_checkpoint = False
    else:
        if verified_pr is None:
            raise ValueError("verified_pr required for non-complete package")
        review = dict(owner_waiver=owner_waiver,
                      independent_review_unavailable=independent_review_unavailable,
                      owner_waiver_source=owner_waiver_source, owner_waiver_reason=owner_waiver_reason)
        evidence = _transition_evidence(plan, verified_pr, source_head, review, root)
        record_checkpoint = True
    updated = decided_transition(plan, candidate=candidate, new_branch=branch,
                                 source_head=source_head, evidence=evidence)
    write_transition(
        plan, updated, evidence, branch=branch, current_branch=current_branch,
        source_head=source_head, root=root, git_fn=git, write_state_fn=write_state,
        record_checkpoint=record_checkpoint,
    )
    return updated, evidence
def reconcile_continuation(plan: dict, *, branch: str, activate: str,
                           reference_head: str, gaps: list[str],
                           root: Path = ROOT) -> dict:
    if git("status", "--porcelain", root=root):
        raise ValueError("reconciliation requires clean checkout")
    problems = verify_checkout(plan, root)
    if problems:
        raise ValueError("; ".join(problems))
    source_head = git("rev-parse", "HEAD", root=root)
    git("cat-file", "-e", f"{reference_head}^{{commit}}", root=root)
    try:
        git("merge-base", "--is-ancestor", reference_head, source_head, root=root)
    except ValueError as exc:
        raise ValueError("reference_head not ancestor of HEAD") from exc
    updated = reconcile_continuation_transition(plan, activate=activate, new_branch=branch,
        source_head=source_head, reference_head=reference_head, acceptance_gaps=gaps)
    paths = state_paths(root)
    originals = {path: path.read_bytes() if path.exists() else None for path in paths}
    original_branch = plan["canonical_lineage"]["working_branch"]
    git("switch", "-c", branch, source_head, root=root)
    try:
        write_state(updated, root=root)
    except Exception:
        for path, data in originals.items():
            if data is None: path.unlink(missing_ok=True)
            else: path.write_bytes(data)
        git("switch", original_branch, root=root)
        git("branch", "-D", branch, root=root)
        raise
    return updated
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    show_one = sub.add_parser("show-package")
    show_one.add_argument("package_id")
    sub.add_parser("verify")
    begin = sub.add_parser("begin-next")
    begin.add_argument("--branch", required=True)
    begin.add_argument("--activate", required=True)
    begin.add_argument("--next", dest="next_id")
    begin.add_argument("--verified-pr", required=True, type=int)
    decided = sub.add_parser("begin-decided-next")
    decided.add_argument("--branch", required=True)
    decided.add_argument("--activate", required=True)
    decided.add_argument("--goal", required=True)
    decided.add_argument("--depends-on", dest="depends_on", action="append", required=True)
    decided.add_argument("--decides-next", action="store_true")
    decided.add_argument("--verified-pr", type=int)
    for p in (begin, decided):
        p.add_argument("--owner-waiver", action="store_true")
        p.add_argument("--independent-review-unavailable", action="store_true")
        p.add_argument("--owner-waiver-source")
        p.add_argument("--owner-waiver-reason")
    rec = sub.add_parser("reconcile-continuation")
    rec.add_argument("--branch", required=True)
    rec.add_argument("--activate", required=True)
    rec.add_argument("--reference-head", required=True)
    rec.add_argument("--gap", dest="gaps", action="append", choices=sorted(RECONCILIATION_GAPS), required=True)
    args = parser.parse_args()
    try:
        plan = load_plan()
        if args.command == "show":
            validate_plan(plan); print(render_current(plan)); return 0
        if args.command == "show-package":
            validate_plan(plan)
            print(json.dumps(show_package(plan, args.package_id), ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify":
            problems = verify_checkout(plan)
            if problems:
                raise ValueError("; ".join(problems))
            print("PROJECT STATE OK"); return 0
        if args.command == "begin-next":
            updated, evidence = begin_next(
                plan, branch=args.branch, activate=args.activate, next_id=args.next_id,
                verified_pr=args.verified_pr, owner_waiver=args.owner_waiver,
                independent_review_unavailable=args.independent_review_unavailable,
                owner_waiver_source=args.owner_waiver_source, owner_waiver_reason=args.owner_waiver_reason)
            print(f"STATE STARTED: active={updated['active_package']} branch={args.branch}")
            print(f"EVIDENCE: {evidence['type']} source={evidence['source_head']} merge={evidence['tested_merge_tree']}")
            return 0
        if args.command == "begin-decided-next":
            candidate = {"id": args.activate, "goal": args.goal, "depends_on": args.depends_on,
                         "decides_next": args.decides_next}
            updated, evidence = begin_decided_next(
                plan, branch=args.branch, candidate=candidate, verified_pr=args.verified_pr,
                owner_waiver=args.owner_waiver,
                independent_review_unavailable=args.independent_review_unavailable,
                owner_waiver_source=args.owner_waiver_source, owner_waiver_reason=args.owner_waiver_reason)
            print(f"STATE STARTED: active={updated['active_package']} branch={args.branch}")
            return 0
        updated = reconcile_continuation(plan, branch=args.branch, activate=args.activate,
            reference_head=args.reference_head, gaps=args.gaps)
        print(f"STATE RECONCILED: active={updated['active_package']} branch={args.branch}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"PROJECT STATE ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["CHECKPOINTS_PATH", "NEXT_PACKAGE_SOURCE_STATUSES", "PACKAGES_PATH", "PLAN_PATH",
    "READY_DEPENDENCY_STATUSES", "ROOT", "active_scope", "begin_decided_next", "begin_next",
    "dependency_problems", "fetch_pr_evidence", "git", "load_checkpoints", "load_plan",
    "render_current", "serialize_checkpoints", "serialize_packages", "serialize_plan", "show_package",
    "transition", "validate_plan", "validate_pr_evidence", "validate_ref", "verify_checkout",
    "write_state"]
