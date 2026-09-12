"""Validate canonical state, low-token routing, block locators and documentation coverage."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from project_state import READY_DEPENDENCY_STATUSES, render_current

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain an object")
    return value


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


def check_current(errors: list[str], plan: dict) -> None:
    actual = (DOCS / "CURRENT.md").read_text(encoding="utf-8")
    expected = render_current(plan)
    if actual != expected:
        errors.append("CURRENT.md must be generated exactly from PLAN.json via project_state.render_current")


def check_context(errors: list[str], context: dict) -> None:
    if context.get("schema_version") != 1:
        errors.append("CONTEXT_MAP schema_version must be 1")
    routes = context.get("routes")
    if not isinstance(routes, dict) or not routes:
        errors.append("CONTEXT_MAP routes must be a non-empty object")
        return
    for key, route in routes.items():
        if not route.get("keywords") or not route.get("read_first"):
            errors.append(f"route {key} requires keywords/read_first")
        for field in ("read_first", "tests", "expand_if_needed", "do_not_read_by_default"):
            for raw in route.get(field, []):
                if not isinstance(raw, str) or not raw or not (ROOT / raw).exists():
                    errors.append(f"route {key}.{field} missing path: {raw}")


def check_blocks(errors: list[str], blocks: dict, context: dict) -> None:
    if blocks.get("schema_version") != 1:
        errors.append("BLOCK_MAP schema_version must be 1")
    for key, block in blocks.get("blocks", {}).items():
        route = block.get("route")
        if route not in context.get("routes", {}):
            errors.append(f"block {key} references unknown route {route}")
        owner = ROOT / str(block.get("owner", ""))
        if not owner.is_file():
            errors.append(f"block {key} owner missing: {block.get('owner')}")
            continue
        anchor = block.get("anchor")
        if not isinstance(anchor, str) or not anchor or anchor not in owner.read_text(encoding="utf-8"):
            errors.append(f"block {key} anchor missing from owner: {anchor}")
        for raw in [*block.get("support", []), *block.get("tests", [])]:
            if not (ROOT / raw).exists():
                errors.append(f"block {key} path missing: {raw}")


def check_coverage(errors: list[str], context: dict) -> None:
    route_paths = {raw for route in context.get("routes", {}).values() for raw in route.get("read_first", [])}
    groups = [ROOT / "apps/web/src/features", ROOT / "apps/api/izo"]
    for base in groups:
        for child in base.iterdir():
            if not child.is_dir() or child.name == "__pycache__":
                continue
            readme = child / "README.md"
            raw = readme.relative_to(ROOT).as_posix()
            if not readme.is_file():
                errors.append(f"local ownership README missing: {raw}")
            elif raw not in route_paths:
                errors.append(f"local ownership README is not covered by a context route: {raw}")
    ownership = {ROOT / raw for raw in route_paths if raw.endswith("README.md")}
    ownership.add(ROOT / "apps/web/security/README.md")
    mutable_sha = re.compile(r"\b[0-9a-f]{40}\b")
    mutable_pr = re.compile(r"\bPR\s*#\d+\b", re.I)
    next_package = re.compile(r"следующ(?:ий|ая|ее).{0,40}пакет", re.I)
    lifecycle_drift = re.compile(r"(?:после\s+acceptance\s+продолжать|остаются\s+демо|для\s+этого\s+нужны\s+(?:CREDIT|MEDIA|JOBS))", re.I)
    for path in ownership:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if mutable_sha.search(text) or mutable_pr.search(text) or next_package.search(text) or lifecycle_drift.search(text):
            errors.append(f"local ownership map contains mutable/history lifecycle language: {path.relative_to(ROOT)}")
        if len(text.encode("utf-8")) > 5000:
            errors.append(f"local ownership map exceeds 5KB context budget: {path.relative_to(ROOT)}")


def check_encoding_and_stable(errors: list[str]) -> None:
    markers = ("РЎ", "Рџ", "Р°", "РЅ", "Рµ", "Рє", "Рё", "Р»", "Рѕ", "СЃ", "С‚", "СЂ", "вЂ", "В·")
    candidates = list(ROOT.rglob("*.md")) + [
        DOCS/"PLAN.json", DOCS/"CONTEXT_MAP.json", DOCS/"BLOCK_MAP.json", ROOT/"tests/context_cases.json",
    ]
    for path in candidates:
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if sum(text.count(marker) for marker in markers) >= 4:
            errors.append(f"possible UTF-8 mojibake: {path.relative_to(ROOT)}")
    stable = [ROOT/"AGENTS.md", ROOT/"README.md", DOCS/"INDEX.md", DOCS/"NEXT.md", DOCS/"DOCS_SYSTEM.md", DOCS/"DEVELOPMENT.md"]
    for path in stable:
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b[0-9a-f]{40}\b", text) or re.search(r"\bPR\s*#\d+\b", text, re.I):
            errors.append(f"stable document contains mutable SHA/PR: {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    try:
        plan = load_json(DOCS/"PLAN.json")
        context = load_json(DOCS/"CONTEXT_MAP.json")
        blocks = load_json(DOCS/"BLOCK_MAP.json")
        check_plan(errors, plan); check_current(errors, plan); check_context(errors, context)
        check_blocks(errors, blocks, context); check_coverage(errors, context); check_encoding_and_stable(errors)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"documentation validation could not complete: {exc}")
    if errors:
        print("DOCS CHECK FAILED"); [print(f"- {error}") for error in errors]; return 1
    print("DOCS CHECK OK")
    print("active=", plan["active_package"], "next=", plan["next_package"], "blocks=", len(blocks["blocks"]), "routes=", len(context["routes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
