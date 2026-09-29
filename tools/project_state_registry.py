"""Bounded live-state and package-registry persistence."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "PLAN.json"
PACKAGES_PATH = ROOT / "docs" / "PACKAGES.json"


def load_live_plan(root: Path = ROOT) -> dict:
    return json.loads((root / "docs" / "PLAN.json").read_text(encoding="utf-8"))


def load_packages(root: Path = ROOT) -> dict:
    path = root / "docs" / "PACKAGES.json"
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("packages"), dict):
            raise ValueError("PACKAGES.json requires a packages object")
        return value["packages"]
    legacy = load_live_plan(root).get("packages")
    if isinstance(legacy, dict):
        return legacy
    raise ValueError("package registry missing")


def load_plan(root: Path = ROOT) -> dict:
    live = load_live_plan(root)
    result = json.loads(json.dumps(live))
    result["packages"] = load_packages(root)
    return result


def serialize_plan(plan: dict) -> str:
    live = {key: value for key, value in plan.items() if key not in {"packages", "status_meaning"}}
    live["packages_ref"] = "PACKAGES.json"
    return json.dumps(live, ensure_ascii=False, indent=2) + "\n"


def serialize_packages(plan: dict) -> str:
    value = {"schema_version": 1, "packages": plan["packages"]}
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


VALID_BASE_STATES = {
    "verified_pr_merge_tree_checkpoint",
    "reconciled_continuation_base",
    "completed_package_successor_base",
}


def validate_live_base(plan: dict) -> None:
    base = plan["canonical_lineage"]["current_package_base"]
    state = base.get("state")
    if state not in VALID_BASE_STATES:
        raise ValueError(f"invalid current_package_base state: {state}")
    if state == "completed_package_successor_base":
        checkpoint = base.get("checkpoint")
        item = plan["packages"].get(checkpoint, {})
        if item.get("status") != "complete" or item.get("checkpoint") != checkpoint:
            raise ValueError("completed successor base requires terminal checkpoint")
