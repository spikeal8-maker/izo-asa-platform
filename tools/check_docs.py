"""Validate canonical state, routing budgets and documentation coverage."""
from __future__ import annotations

import json
import re

from docs_context import DOCS, ROOT, check_blocks, check_context, check_coverage, load_json, load_map
from project_state import READY_DEPENDENCY_STATUSES, render_current


def check_ref(errors: list[str], label: str, value: dict) -> None:
    if not isinstance(value, dict) or not value.get("branch"):
        errors.append(f"{label} requires branch")
        return
    if not re.fullmatch(r"[0-9a-f]{40}", str(value.get("sha", ""))):
        errors.append(f"{label} requires full SHA")


def check_plan(errors: list[str], plan: dict) -> None:
    if plan.get("schema_version") != 1:
        errors.append("PLAN schema_version must be 1")
    packages = plan.get("packages", {})
    active_id = plan.get("active_package")
    active = [key for key, item in packages.items() if item.get("status") == "active"]
    if active != [active_id]:
        errors.append(f"exactly one active package must match active_package: {active}")
    next_id = plan.get("next_package")
    if next_id is None:
        if not packages.get(active_id, {}).get("decides_next"):
            errors.append("next_package may be null only when active package has decides_next=true")
    elif next_id not in packages or packages.get(next_id, {}).get("status") != "planned_next":
        errors.append("PLAN next_package must exist with status planned_next")
    elif active_id not in packages[next_id].get("depends_on", []):
        errors.append("planned_next package must depend on the active package")
    for key, item in packages.items():
        deps = item.get("depends_on", [])
        if not isinstance(deps, list) or any(dep not in packages or dep == key for dep in deps):
            errors.append(f"invalid dependencies for {key}: {deps}")
        if "evidence" in item:
            errors.append(f"package {key} embeds CI evidence; use CHECKPOINTS.json")
    for dep in packages.get(active_id, {}).get("depends_on", []):
        if packages.get(dep, {}).get("status") not in READY_DEPENDENCY_STATUSES:
            errors.append(f"active package dependency is not ready: {dep}={packages.get(dep, {}).get('status')}")
    lineage = plan.get("canonical_lineage", {})
    check_ref(errors, "canonical_lineage.runtime_base", lineage.get("runtime_base", {}))
    check_ref(errors, "canonical_lineage.current_package_base", lineage.get("current_package_base", {}))
    if lineage.get("next_branch_source") != "verified_working_head":
        errors.append("canonical_lineage.next_branch_source must be verified_working_head")
    if not lineage.get("working_branch"):
        errors.append("canonical_lineage.working_branch is required")
    for item in plan.get("parallel_lineages", []):
        if not item.get("do_not_continue_automatically"):
            errors.append(f"parallel lineage {item.get('id')} must fail closed")


def check_checkpoints(errors: list[str], plan: dict, checkpoints: dict) -> None:
    if checkpoints.get("schema_version") != 1 or not isinstance(checkpoints.get("checkpoints"), dict):
        errors.append("CHECKPOINTS schema_version/checkpoints invalid")
        return
    registry = checkpoints["checkpoints"]
    for package_id, item in plan.get("packages", {}).items():
        ref = item.get("checkpoint")
        if ref is not None and (ref != package_id or ref not in registry):
            errors.append(f"package {package_id} has invalid checkpoint ref: {ref}")
    for key, evidence in registry.items():
        if not isinstance(evidence, dict):
            errors.append(f"checkpoint {key} must be an object")
            continue
        source = evidence.get("source_head", evidence.get("head"))
        if not re.fullmatch(r"[0-9a-f]{40}", str(source or "")):
            errors.append(f"checkpoint {key} requires a full source/head SHA")


def check_current(errors: list[str], plan: dict) -> None:
    actual = (DOCS / "CURRENT.md").read_text(encoding="utf-8")
    if actual != render_current(plan):
        errors.append("CURRENT.md must be generated exactly from PLAN.json via project_state.render_current")


def check_encoding_and_stable(errors: list[str]) -> None:
    markers = ("РЎ", "Рџ", "Р°", "РЅ", "Рµ", "Рє", "Рё", "Р»", "Рѕ", "СЃ", "С‚", "СЂ", "вЂ", "В·")
    candidates = list(ROOT.rglob("*.md")) + [
        DOCS / "PLAN.json", DOCS / "CHECKPOINTS.json", DOCS / "CONTEXT_MAP.json",
        DOCS / "BLOCK_MAP.json", ROOT / "tests/context_cases.json"]
    for path in candidates:
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if sum(text.count(marker) for marker in markers) >= 4:
            errors.append(f"possible UTF-8 mojibake: {path.relative_to(ROOT)}")
    stable = [ROOT / "AGENTS.md", ROOT / "README.md", DOCS / "INDEX.md", DOCS / "NEXT.md",
              DOCS / "DOCS_SYSTEM.md", DOCS / "DEVELOPMENT.md", DOCS / "MAINTAINABILITY.md"]
    for path in stable:
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b[0-9a-f]{40}\b", text) or re.search(r"\bPR\s*#\d+\b", text, re.I):
            errors.append(f"stable document contains mutable SHA/PR: {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    try:
        plan = load_json(DOCS / "PLAN.json")
        checkpoints = load_json(DOCS / "CHECKPOINTS.json")
        context, context_sources = load_map(DOCS / "CONTEXT_MAP.json", "routes")
        blocks, block_sources = load_map(DOCS / "BLOCK_MAP.json", "blocks")
        check_plan(errors, plan); check_checkpoints(errors, plan, checkpoints)
        check_current(errors, plan); check_context(errors, context, context_sources)
        check_blocks(errors, blocks, context, block_sources); check_coverage(errors, context)
        check_encoding_and_stable(errors)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"documentation validation could not complete: {exc}")
    if errors:
        print("DOCS CHECK FAILED"); [print(f"- {error}") for error in errors]; return 1
    print("DOCS CHECK OK")
    print("active=", plan["active_package"], "next=", plan["next_package"],
          "blocks=", len(blocks["blocks"]), "routes=", len(context["routes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
