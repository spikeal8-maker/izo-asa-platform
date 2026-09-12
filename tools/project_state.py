"""Inspect IZO ASA state and start the next package from verified GitHub evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "PLAN.json"
REQUIRED_WORKFLOWS = ("Foundation CI", "Dependency Security", "Review Source")
READY_DEPENDENCY_STATUSES = {
    "technical_pass",
    "technical_ci_pass_live_acceptance_pending",
    "historical_complete",
    "historical_technical_pass",
}
NEXT_PACKAGE_SOURCE_STATUSES = {"planned"}


def load_plan(root: Path = ROOT) -> dict:
    return json.loads((root / "docs" / "PLAN.json").read_text(encoding="utf-8"))


def run(args: list[str], *, root: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"command failed: {' '.join(args)}")
    return result.stdout.strip()


def git(*args: str, root: Path = ROOT) -> str:
    return run(["git", *args], root=root)


def repo_slug(root: Path = ROOT) -> str:
    remote = git("remote", "get-url", "origin", root=root).strip()
    if remote.startswith("git@github.com:"):
        value = remote.split(":", 1)[1]
    else:
        parsed = urlparse(remote)
        if parsed.hostname != "github.com":
            raise ValueError("origin must point to github.com")
        value = parsed.path.lstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if value.count("/") != 1:
        raise ValueError("cannot derive owner/repo from origin")
    return value


def gh_json(args: list[str], *, root: Path = ROOT):
    text = run(["gh", *args], root=root)
    return json.loads(text)


def foundation_tested_sha(run_id: int, slug: str, *, root: Path = ROOT) -> str:
    log = run(["gh", "run", "view", str(run_id), "--repo", slug, "--log"], root=root)
    values = set(re.findall(r"IZO_BUILD_SHA:\s*([0-9a-f]{40})", log))
    if len(values) != 1:
        raise ValueError(f"Foundation CI {run_id} does not expose one tested IZO_BUILD_SHA: {sorted(values)}")
    return values.pop()


def merge_ref_sha(pr_number: int, *, root: Path = ROOT) -> str:
    text = git("ls-remote", "origin", f"refs/pull/{pr_number}/merge", root=root)
    sha = text.split()[0] if text else ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError(f"PR #{pr_number} has no resolvable merge ref")
    return sha


def validate_pr_evidence(*, pr: dict, runs: list[dict], merge_sha: str,
                         merge_commit: dict, expected_head: str, pr_number: int,
                         foundation_tree: str) -> dict:
    if pr.get("headRefOid") != expected_head:
        raise ValueError(f"PR #{pr_number} head {pr.get('headRefOid')} != expected {expected_head}")
    if str(pr.get("state", "")).upper() != "OPEN":
        raise ValueError(f"PR #{pr_number} must still be open while used as checkpoint evidence")
    successful: dict[str, int] = {}
    for name in REQUIRED_WORKFLOWS:
        candidates = [item for item in runs if item.get("name") == name and item.get("headSha") == expected_head]
        passed = [item for item in candidates if item.get("event") == "pull_request" and item.get("conclusion") == "success"]
        if not passed:
            raise ValueError(f"required workflow {name!r} is not successful for source head {expected_head}")
        successful[name] = int(passed[0]["databaseId"])
    parents = [item.get("sha") for item in merge_commit.get("parents", [])]
    base_head = pr.get("baseRefOid")
    if expected_head not in parents or base_head not in parents:
        raise ValueError(f"PR merge tree {merge_sha} does not contain current source/base parents")
    if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        raise ValueError("merge tree SHA is invalid")
    if foundation_tree != merge_sha:
        raise ValueError(f"Foundation CI tested merge tree {foundation_tree}, current PR merge tree is {merge_sha}")
    return {
        "type": "pr_merge_tree",
        "source_head": expected_head,
        "verified_pr": pr_number,
        "base_head": pr.get("baseRefOid"),
        "tested_merge_tree": merge_sha,
        "workflows": successful,
    }


def fetch_pr_evidence(pr_number: int, expected_head: str, *, root: Path = ROOT) -> dict:
    slug = repo_slug(root)
    pr = gh_json([
        "pr", "view", str(pr_number), "--repo", slug,
        "--json", "headRefOid,baseRefOid,isDraft,state,url",
    ], root=root)
    runs = gh_json([
        "run", "list", "--repo", slug, "--commit", expected_head,
        "--event", "pull_request", "--json", "databaseId,name,conclusion,headSha,event", "--limit", "30",
    ], root=root)
    merge_sha = merge_ref_sha(pr_number, root=root)
    merge_commit = gh_json(["api", f"repos/{slug}/commits/{merge_sha}"], root=root)
    foundation = next(
        (item for item in runs
         if item.get("name") == "Foundation CI" and item.get("headSha") == expected_head
         and item.get("event") == "pull_request" and item.get("conclusion") == "success"),
        None,
    )
    if foundation is None:
        raise ValueError(f"required workflow 'Foundation CI' is not successful for source head {expected_head}")
    foundation_tree = foundation_tested_sha(int(foundation["databaseId"]), slug, root=root)
    return validate_pr_evidence(
        pr=pr, runs=runs, merge_sha=merge_sha, merge_commit=merge_commit,
        expected_head=expected_head, pr_number=pr_number, foundation_tree=foundation_tree,
    )


def render_current(plan: dict) -> str:
    lineage = plan["canonical_lineage"]
    runtime = lineage["runtime_base"]
    base = lineage["current_package_base"]
    active, next_id = plan["active_package"], plan.get("next_package")
    next_text = next_id or "NONE"
    return f'''# IZO ASA · текущая точка разработки

<!-- runtime_base={runtime["branch"]}@{runtime["sha"]} -->
<!-- current_package_base={base["branch"]}@{base["sha"]} -->
<!-- working_branch={lineage["working_branch"]} -->
<!-- active_package={active} -->
<!-- next_package={next_text} -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Следующий package стартует командой `python tools/project_state.py begin-next ...`: она проверяет GitHub PR
и required workflows текущего working head, создаёт новую ветку точно от этого head и только там меняет state.

Активный пакет: **{active}**. Следующий: **{next_text}**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
'''


def validate_ref(label: str, value: dict) -> None:
    if not isinstance(value, dict) or not value.get("branch"):
        raise ValueError(f"{label} requires branch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(value.get("sha", ""))):
        raise ValueError(f"{label} requires full SHA")


def validate_plan(plan: dict) -> None:
    lineage = plan.get("canonical_lineage", {})
    validate_ref("canonical_lineage.runtime_base", lineage.get("runtime_base", {}))
    validate_ref("canonical_lineage.current_package_base", lineage.get("current_package_base", {}))
    if lineage.get("next_branch_source") != "verified_working_head":
        raise ValueError("next_branch_source must be verified_working_head")
    if not lineage.get("working_branch"):
        raise ValueError("canonical_lineage.working_branch is required")
    packages = plan.get("packages", {})
    active_id = plan.get("active_package")
    active = [key for key, item in packages.items() if item.get("status") == "active"]
    if active != [active_id]:
        raise ValueError(f"exactly one active package required: {active}")
    for key, item in packages.items():
        deps = item.get("depends_on", [])
        if not isinstance(deps, list) or any(dep not in packages or dep == key for dep in deps):
            raise ValueError(f"invalid dependencies for {key}: {deps}")
    for dep in packages.get(active_id, {}).get("depends_on", []):
        if packages[dep].get("status") not in READY_DEPENDENCY_STATUSES:
            raise ValueError(f"active package dependency is not ready: {dep}={packages[dep].get('status')}")
    next_id = plan.get("next_package")
    if next_id is None:
        if not packages.get(active_id, {}).get("decides_next"):
            raise ValueError("next_package may be null only for an active decides_next package")
    elif next_id not in packages or packages[next_id].get("status") != "planned_next":
        raise ValueError("next_package must exist with status planned_next")
    elif active_id not in packages[next_id].get("depends_on", []):
        raise ValueError("next_package must directly depend on the active package")


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


def dependency_problems(plan: dict, activate: str, *, finishing: str) -> list[str]:
    packages = plan["packages"]
    item = packages.get(activate)
    if not item:
        return [f"unknown package {activate}"]
    problems = []
    deps = item.get("depends_on", [])
    if finishing not in deps:
        problems.append(f"{activate} must directly depend on finishing package {finishing}")
    for dep in deps:
        status = "technical_pass" if dep == finishing else packages.get(dep, {}).get("status")
        if status not in READY_DEPENDENCY_STATUSES:
            problems.append(f"dependency {dep} is not ready: {status}")
    return problems


def transition(plan: dict, *, activate: str, next_id: str | None,
               new_branch: str, source_head: str, evidence: dict) -> dict:
    validate_plan(plan)
    active = plan["active_package"]
    if plan.get("next_package") != activate:
        raise ValueError(f"{activate} is not PLAN next_package")
    problems = dependency_problems(plan, activate, finishing=active)
    if problems:
        raise ValueError("; ".join(problems))
    if next_id is not None:
        next_item = plan["packages"].get(next_id)
        if next_item is None:
            raise ValueError(f"unknown next package {next_id}")
        if next_id in {active, activate}:
            raise ValueError("next package must differ from finishing and activating packages")
        if next_item.get("status") not in NEXT_PACKAGE_SOURCE_STATUSES:
            raise ValueError(f"next package {next_id} is not eligible from status {next_item.get('status')}")
        if activate not in next_item.get("depends_on", []):
            raise ValueError(f"next package {next_id} must directly depend on activating package {activate}")
    result = json.loads(json.dumps(plan))
    result["packages"][active]["status"] = "technical_pass"
    result["packages"][active]["evidence"] = evidence
    result["packages"][activate]["status"] = "active"
    result["active_package"] = activate
    result["next_package"] = next_id
    lineage = result["canonical_lineage"]
    lineage["current_package_base"] = {
        "branch": lineage["working_branch"],
        "sha": source_head,
        "state": "verified_pr_merge_tree_checkpoint",
    }
    lineage["working_branch"] = new_branch
    if next_id is not None:
        result["packages"][next_id]["status"] = "planned_next"
    validate_plan(result)
    return result


def serialize_plan(plan: dict) -> str:
    lines = ["{"]
    keys = list(plan)
    for index, key in enumerate(keys):
        value = plan[key]
        comma = "," if index < len(keys) - 1 else ""
        if key in {"packages", "status_meaning"} and isinstance(value, dict):
            lines.append(f'  {json.dumps(key)}: {{')
            items = list(value.items())
            for pos, (name, item) in enumerate(items):
                tail = "," if pos < len(items) - 1 else ""
                compact = json.dumps(item, ensure_ascii=False, separators=(",", ": "))
                lines.append(f'    {json.dumps(name, ensure_ascii=False)}: {compact}{tail}')
            lines.append(f"  }}{comma}")
        else:
            rendered = json.dumps(value, ensure_ascii=False, indent=2).splitlines()
            if len(rendered) == 1:
                lines.append(f'  {json.dumps(key)}: {rendered[0]}{comma}')
            else:
                lines.append(f'  {json.dumps(key)}: {rendered[0]}')
                lines.extend("  " + line for line in rendered[1:-1])
                lines.append("  " + rendered[-1] + comma)
    return "\n".join([*lines, "}"]) + "\n"


def write_state(plan: dict, root: Path = ROOT) -> None:
    (root / "docs" / "PLAN.json").write_bytes(serialize_plan(plan).encode("utf-8"))
    (root / "docs" / "CURRENT.md").write_bytes(render_current(plan).encode("utf-8"))


def begin_next(plan: dict, *, branch: str, activate: str, next_id: str | None,
               verified_pr: int, root: Path = ROOT) -> tuple[dict, dict]:
    validate_plan(plan)
    if git("status", "--porcelain", root=root):
        raise ValueError("begin-next requires a clean checkout")
    current_branch = git("branch", "--show-current", root=root)
    if current_branch != plan["canonical_lineage"]["working_branch"]:
        raise ValueError("begin-next must run from the current working_branch")
    source_head = git("rev-parse", "HEAD", root=root)
    evidence = fetch_pr_evidence(verified_pr, source_head, root=root)
    if branch == current_branch:
        raise ValueError("next package requires a new branch")
    updated = transition(
        plan, activate=activate, next_id=next_id, new_branch=branch,
        source_head=source_head, evidence=evidence,
    )
    plan_bytes = (root / "docs" / "PLAN.json").read_bytes()
    current_bytes = (root / "docs" / "CURRENT.md").read_bytes()
    git("switch", "-c", branch, source_head, root=root)
    try:
        write_state(updated, root=root)
    except Exception:
        (root / "docs" / "PLAN.json").write_bytes(plan_bytes)
        (root / "docs" / "CURRENT.md").write_bytes(current_bytes)
        git("switch", current_branch, root=root)
        git("branch", "-D", branch, root=root)
        raise
    return updated, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    sub.add_parser("verify")
    begin = sub.add_parser("begin-next")
    begin.add_argument("--branch", required=True)
    begin.add_argument("--activate", required=True)
    begin.add_argument("--next", dest="next_id")
    begin.add_argument("--verified-pr", required=True, type=int)
    args = parser.parse_args()
    try:
        plan = load_plan()
        if args.command == "show":
            validate_plan(plan)
            print(render_current(plan))
            return 0
        if args.command == "verify":
            problems = verify_checkout(plan)
            if problems:
                raise ValueError("; ".join(problems))
            print("PROJECT STATE OK")
            return 0
        updated, evidence = begin_next(
            plan, branch=args.branch, activate=args.activate, next_id=args.next_id,
            verified_pr=args.verified_pr,
        )
        print(f"STATE STARTED: active={updated['active_package']} branch={args.branch}")
        print(f"EVIDENCE: {evidence['type']} source={evidence['source_head']} merge={evidence['tested_merge_tree']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"PROJECT STATE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
