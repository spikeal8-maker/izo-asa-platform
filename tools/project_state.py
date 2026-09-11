"""Inspect and safely advance IZO ASA development state from a frozen checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "PLAN.json"
CURRENT_PATH = ROOT / "docs" / "CURRENT.md"


def load_plan(root: Path = ROOT) -> dict:
    return json.loads((root / "docs" / "PLAN.json").read_text(encoding="utf-8"))


def git(*args: str, root: Path = ROOT) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def render_current(plan: dict) -> str:
    lineage = plan["canonical_lineage"]
    runtime = lineage["runtime_base"]
    parent = lineage["branch_from"]
    active, next_id = plan["active_package"], plan.get("next_package")
    next_text = next_id or "NONE"
    return f'''# IZO ASA · текущая точка разработки

<!-- runtime_base={runtime["branch"]}@{runtime["sha"]} -->
<!-- branch_from={parent["branch"]}@{parent["sha"]} -->
<!-- working_branch={lineage["working_branch"]} -->
<!-- active_package={active} -->
<!-- next_package={next_text} -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Откуда продолжать

Новые изменения создаются только от **branch_from** выше. `runtime_base` — принятая runtime-основа,
но не обязательно последний development checkpoint. Текущая рабочая ветка — `working_branch`.

Активный пакет: **{active}**. Следующий: **{next_text}**.

Параллельные lineages из PLAN нельзя использовать как base без отдельного reconciliation.
Зелёный exact-head CI замораживает checkpoint: после него этот SHA не редактируется.
Следующий пакет начинает новая ветка от frozen SHA и переводит состояние через `tools/project_state.py start`.
'''


def validate_plan(plan: dict) -> None:
    lineage = plan.get("canonical_lineage", {})
    for name in ("runtime_base", "branch_from"):
        value = lineage.get(name, {})
        if not value.get("branch") or not re.fullmatch(r"[0-9a-f]{40}", str(value.get("sha", ""))):
            raise ValueError(f"canonical_lineage.{name} requires branch and full SHA")
    if not lineage.get("working_branch"):
        raise ValueError("canonical_lineage.working_branch is required")
    packages = plan.get("packages", {})
    active = [key for key, item in packages.items() if item.get("status") == "active"]
    active_id = plan.get("active_package")
    if active != [active_id]:
        raise ValueError(f"exactly one active package required: {active}")
    next_id = plan.get("next_package")
    if next_id is None:
        if not packages.get(active_id, {}).get("decides_next"):
            raise ValueError("next_package may be null only for an active decides_next package")
    elif next_id not in packages or packages[next_id].get("status") != "planned_next":
        raise ValueError("next_package must exist with status planned_next")


def verify_checkout(plan: dict, root: Path = ROOT) -> list[str]:
    validate_plan(plan)
    problems: list[str] = []
    lineage = plan["canonical_lineage"]
    branch = git("branch", "--show-current", root=root)
    head = git("rev-parse", "HEAD", root=root)
    parent = lineage["branch_from"]
    try:
        git("merge-base", "--is-ancestor", parent["sha"], head, root=root)
    except ValueError:
        problems.append(f"HEAD {head} is not descended from branch_from {parent['sha']}")
    if branch != lineage["working_branch"]:
        problems.append(f"checkout branch {branch} != PLAN working_branch {lineage['working_branch']}")
    return problems


def start_transition(plan: dict, *, current_branch: str, current_head: str,
                     activate: str, next_id: str | None, foundation_ci: int) -> dict:
    validate_plan(plan)
    active = plan["active_package"]
    if not re.fullmatch(r"[0-9a-f]{40}", current_head) or foundation_ci <= 0:
        raise ValueError("transition requires verified full head SHA and positive Foundation CI id")
    if plan.get("next_package") != activate:
        raise ValueError(f"{activate} is not PLAN next_package")
    working = plan["canonical_lineage"]["working_branch"]
    if current_branch == working:
        raise ValueError("new package must use a new branch, not mutate the frozen checkpoint branch")
    result = json.loads(json.dumps(plan))
    result["packages"][active]["status"] = "technical_pass"
    result["packages"][active]["evidence"] = {
        "head": current_head,
        "foundation_ci": foundation_ci,
    }
    result["packages"][activate]["status"] = "active"
    result["active_package"] = activate
    result["next_package"] = next_id
    lineage = result["canonical_lineage"]
    lineage["branch_from"] = {
        "branch": working,
        "sha": current_head,
        "state": "verified_checkpoint",
    }
    lineage["working_branch"] = current_branch
    if next_id is not None:
        if next_id not in result["packages"]:
            raise ValueError(f"unknown next package {next_id}")
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
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
            rendered_lines = rendered.splitlines()
            if len(rendered_lines) == 1:
                lines.append(f'  {json.dumps(key)}: {rendered}{comma}')
            else:
                lines.append(f'  {json.dumps(key)}: {rendered_lines[0]}')
                lines.extend("  " + line for line in rendered_lines[1:-1])
                lines.append("  " + rendered_lines[-1] + comma)
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_state(plan: dict, root: Path = ROOT) -> None:
    current_text = render_current(plan)
    (root / "docs" / "PLAN.json").write_bytes(serialize_plan(plan).encode("utf-8"))
    (root / "docs" / "CURRENT.md").write_bytes(current_text.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    sub.add_parser("verify")
    start = sub.add_parser("start")
    start.add_argument("--activate", required=True)
    start.add_argument("--next", dest="next_id")
    start.add_argument("--verified-sha", required=True)
    start.add_argument("--foundation-ci", required=True, type=int)
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
        if git("status", "--porcelain"):
            raise ValueError("start requires a clean checkout at the frozen checkpoint")
        branch = git("branch", "--show-current")
        head = git("rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", args.verified_sha) or args.verified_sha != head:
            raise ValueError("--verified-sha must equal the exact current frozen HEAD")
        parent = plan["canonical_lineage"]["branch_from"]["sha"]
        git("merge-base", "--is-ancestor", parent, head)
        updated = start_transition(
            plan,
            current_branch=branch,
            current_head=head,
            activate=args.activate,
            next_id=args.next_id,
            foundation_ci=args.foundation_ci,
        )
        write_state(updated)
        print(f"STATE STARTED: active={args.activate} branch={branch} from={head}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"PROJECT STATE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
