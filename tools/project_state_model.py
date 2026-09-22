"""Pure project-state model: validation, transitions and deterministic serialization."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "PLAN.json"
CHECKPOINTS_PATH = ROOT / "docs" / "CHECKPOINTS.json"
READY_DEPENDENCY_STATUSES = {
    "technical_pass",
    "technical_ci_pass_live_acceptance_pending",
    "historical_complete",
    "historical_technical_pass",
}
NEXT_PACKAGE_SOURCE_STATUSES = {"planned"}
RECONCILIATION_GAPS = {
    "scope", "independent_review", "owner_visual_acceptance",
    "ci", "runtime", "operational",
}
INCOMPLETE_REFERENCE_STATUS = "superseded_incomplete_reference"


def load_plan(root: Path = ROOT) -> dict:
    return json.loads((root / "docs" / "PLAN.json").read_text(encoding="utf-8"))


def load_checkpoints(root: Path = ROOT) -> dict:
    path = root / "docs" / "CHECKPOINTS.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": 1, "checkpoints": {}}


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
Если `next_package` выбран — `begin-next`. Для `decides_next=true` + `next_package=NONE` —
`begin-decided-next`: exact HEAD/CI/review или explicit owner waiver проверяются до новой ветки, state пишется только
на ней. Для непринятого active package используется только `reconcile-continuation`.

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
        continues = item.get("continues")
        if continues is not None and (continues not in packages or continues == key):
            raise ValueError(f"invalid continuation for {key}: {continues}")
        superseded_by = item.get("superseded_by")
        if superseded_by is not None and (superseded_by not in packages or superseded_by == key):
            raise ValueError(f"invalid superseded_by for {key}: {superseded_by}")
        if item.get("status") == INCOMPLETE_REFERENCE_STATUS:
            reference = str(item.get("reference_head", ""))
            gaps = item.get("acceptance_gaps")
            if not re.fullmatch(r"[0-9a-f]{40}", reference):
                raise ValueError(f"{key} requires reference_head")
            if (not isinstance(gaps, list) or not gaps or len(set(gaps)) != len(gaps)
                    or any(gap not in RECONCILIATION_GAPS for gap in gaps)):
                raise ValueError(f"{key} requires valid acceptance_gaps")
            if superseded_by is None or packages[superseded_by].get("continues") != key:
                raise ValueError(f"{key} requires reciprocal continuation")
            if "checkpoint" in item:
                raise ValueError(f"{key} cannot have checkpoint")
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
    result["packages"][active]["checkpoint"] = active
    result["packages"][active].pop("evidence", None)
    result["packages"][activate]["status"] = "active"
    result["active_package"] = activate
    result["next_package"] = next_id
    lineage = result["canonical_lineage"]
    lineage["current_package_base"] = {
        "branch": lineage["working_branch"], "sha": source_head,
        "state": "verified_pr_merge_tree_checkpoint"}
    lineage["working_branch"] = new_branch
    if next_id is not None:
        result["packages"][next_id]["status"] = "planned_next"
    validate_plan(result)
    return result


def reconcile_continuation_transition(plan: dict, *, activate: str, new_branch: str,
                                      source_head: str, reference_head: str,
                                      acceptance_gaps: list[str]) -> dict:
    validate_plan(plan)
    active = plan["active_package"]
    packages = plan["packages"]
    if plan.get("next_package") is not None:
        raise ValueError("reconciliation requires next_package=null")
    if not packages[active].get("decides_next"):
        raise ValueError("active package must decide next")
    target = packages.get(activate)
    if target is None or target.get("status") != "planned":
        raise ValueError(f"{activate} must exist with status planned")
    if target.get("continues") != active:
        raise ValueError(f"{activate} must continue active package {active}")
    if new_branch == plan["canonical_lineage"]["working_branch"]:
        raise ValueError("new branch required")
    if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in (source_head, reference_head)):
        raise ValueError("source/reference head requires full lowercase SHA")
    if reference_head == source_head:
        raise ValueError("same source: use normal lifecycle")
    if (not acceptance_gaps or len(set(acceptance_gaps)) != len(acceptance_gaps)
            or any(gap not in RECONCILIATION_GAPS for gap in acceptance_gaps)):
        raise ValueError("invalid gaps")
    for dep in target.get("depends_on", []):
        status = packages[dep].get("status")
        if status not in READY_DEPENDENCY_STATUSES:
            raise ValueError(f"dependency {dep} is not ready: {status}")

    result = json.loads(json.dumps(plan))
    old = result["packages"][active]
    old.update(status=INCOMPLETE_REFERENCE_STATUS, reference_head=reference_head,
               acceptance_gaps=list(acceptance_gaps), superseded_by=activate)
    old.pop("checkpoint", None)
    old.pop("evidence", None)
    result["packages"][activate]["status"] = "active"
    result["active_package"] = activate
    result["next_package"] = None
    lineage = result["canonical_lineage"]
    lineage["current_package_base"] = {
        "branch": lineage["working_branch"], "sha": source_head,
        "state": "reconciled_continuation_base"}
    lineage["working_branch"] = new_branch
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


def serialize_checkpoints(checkpoints: dict) -> str:
    return json.dumps(checkpoints, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_state(plan: dict, checkpoints: dict | None = None, root: Path = ROOT) -> None:
    (root / "docs" / "PLAN.json").write_bytes(serialize_plan(plan).encode("utf-8"))
    (root / "docs" / "CURRENT.md").write_bytes(render_current(plan).encode("utf-8"))
    if checkpoints is not None:
        (root / "docs" / "CHECKPOINTS.json").write_bytes(
            serialize_checkpoints(checkpoints).encode("utf-8"))
