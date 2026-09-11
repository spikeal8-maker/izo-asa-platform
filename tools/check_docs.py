"""Validate IZO ASA documentation routing and canonical development state."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def current_marker(text: str, name: str) -> str | None:
    match = re.search(rf"<!--\s*{re.escape(name)}=([^\s]+)\s*-->", text)
    return match.group(1) if match else None


def check_plan(errors: list[str], plan: dict) -> None:
    if plan.get("schema_version") != 1:
        errors.append("PLAN schema_version must be 1")
    packages = plan.get("packages")
    if not isinstance(packages, dict) or not packages:
        errors.append("PLAN packages must be a non-empty object")
        return
    active = [key for key, item in packages.items() if item.get("status") == "active"]
    if active != [plan.get("active_package")]:
        errors.append(f"PLAN must have exactly one active package matching active_package: {active}")
    next_id = plan.get("next_package")
    if next_id not in packages or packages.get(next_id, {}).get("status") != "planned_next":
        errors.append("PLAN next_package must exist with status planned_next")
    for key, item in packages.items():
        deps = item.get("depends_on", [])
        if not isinstance(deps, list):
            errors.append(f"{key}.depends_on must be a list")
            continue
        for dep in deps:
            if dep not in packages:
                errors.append(f"{key} depends on unknown package {dep}")
            if dep == key:
                errors.append(f"{key} cannot depend on itself")
    lineage = plan.get("canonical_lineage", {})
    if not re.fullmatch(r"[0-9a-f]{40}", str(lineage.get("baseline_sha", ""))):
        errors.append("canonical_lineage.baseline_sha must be a full commit SHA")
    parallels = plan.get("parallel_lineages", [])
    if not isinstance(parallels, list):
        errors.append("parallel_lineages must be a list")
    else:
        for item in parallels:
            if not item.get("do_not_continue_automatically"):
                errors.append(f"parallel lineage {item.get('id')} must be fail-closed for automatic continuation")


def check_current(errors: list[str], plan: dict) -> None:
    text = (DOCS / "CURRENT.md").read_text(encoding="utf-8")
    expected = {
        "canonical_branch": plan.get("canonical_lineage", {}).get("baseline_branch"),
        "canonical_baseline_sha": plan.get("canonical_lineage", {}).get("baseline_sha"),
        "active_package": plan.get("active_package"),
        "next_package": plan.get("next_package"),
    }
    for name, value in expected.items():
        if current_marker(text, name) != value:
            errors.append(f"CURRENT marker {name} does not match PLAN")


def check_context(errors: list[str], context: dict) -> None:
    if context.get("schema_version") != 1:
        errors.append("CONTEXT_MAP schema_version must be 1")
    routes = context.get("routes")
    if not isinstance(routes, dict) or not routes:
        errors.append("CONTEXT_MAP routes must be a non-empty object")
        return
    for key, route in routes.items():
        if not route.get("keywords") or not route.get("read_first"):
            errors.append(f"context route {key} requires keywords and read_first")
        for field in ("read_first", "tests", "expand_if_needed", "do_not_read_by_default"):
            for raw in route.get(field, []):
                if not isinstance(raw, str) or not raw:
                    errors.append(f"context route {key}.{field} contains an invalid path")
                    continue
                path = ROOT / raw
                if not path.exists():
                    errors.append(f"context route {key}.{field} points to missing path: {raw}")

def check_local_maps(errors: list[str]) -> None:
    required = [
        "apps/web/src/features/accounts/README.md",
        "apps/web/src/features/admin/README.md",
        "apps/web/src/features/credits/README.md",
        "apps/web/src/features/gallery/README.md",
        "apps/web/src/features/studio/README.md",
        "apps/api/izo/providers/README.md",
        "apps/api/izo/providers/AGENTS.md",
    ]
    for raw in required:
        if not (ROOT / raw).is_file():
            errors.append(f"required local ownership map missing: {raw}")


def check_encoding(errors: list[str]) -> None:
    markers = ("РЎ", "Рџ", "Р°", "вЂ", "В·")
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if sum(text.count(marker) for marker in markers) >= 8:
            errors.append(f"possible UTF-8 mojibake: {path.relative_to(ROOT)}")


def check_stable_docs(errors: list[str]) -> None:
    stable = [ROOT / "AGENTS.md", ROOT / "README.md", DOCS / "INDEX.md", DOCS / "DOCS_SYSTEM.md", DOCS / "DEVELOPMENT.md"]
    sha = re.compile(r"\b[0-9a-f]{40}\b")
    pr = re.compile(r"\bPR\s*#\d+\b", re.IGNORECASE)
    for path in stable:
        text = path.read_text(encoding="utf-8")
        if sha.search(text):
            errors.append(f"stable document contains mutable SHA: {path.relative_to(ROOT)}")
        if pr.search(text):
            errors.append(f"stable document contains mutable PR reference: {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    try:
        plan = load_json(DOCS / "PLAN.json")
        context = load_json(DOCS / "CONTEXT_MAP.json")
        check_plan(errors, plan)
        check_current(errors, plan)
        check_context(errors, context)
        check_local_maps(errors)
        check_encoding(errors)
        check_stable_docs(errors)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"documentation validation could not complete: {exc}")
    if errors:
        print("DOCS CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("DOCS CHECK OK")
    print("canonical=", plan["canonical_lineage"]["baseline_branch"])
    print("active=", plan["active_package"], "next=", plan["next_package"])
    print("context_routes=", len(context["routes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
