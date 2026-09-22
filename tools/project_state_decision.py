"""Pure dynamic owner-decision transition for decides_next packages."""
from __future__ import annotations
import json
import re

from project_state_model import dependency_problems, validate_plan

PACKAGE_ID_RE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")
MAX_GOAL = 600
MAX_DEPENDENCIES = 12
_FIELDS = {"id", "goal", "depends_on", "decides_next"}


def _normalize_spec(spec: dict, *, finishing: str) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("decided package spec must be an object")
    keys = set(spec)
    if keys != _FIELDS:
        raise ValueError(
            f"decided package spec fields invalid: unknown={sorted(keys - _FIELDS)} "
            f"missing={sorted(_FIELDS - keys)}")
    package_id, goal, deps = spec["id"], spec["goal"], spec["depends_on"]
    if not isinstance(package_id, str) or not PACKAGE_ID_RE.fullmatch(package_id):
        raise ValueError("decided package id is invalid")
    if not isinstance(goal, str) or not goal.strip() or len(goal.strip()) > MAX_GOAL:
        raise ValueError("decided package goal must be non-empty and bounded")
    if (not isinstance(deps, list) or not deps or len(deps) > MAX_DEPENDENCIES
            or any(not isinstance(dep, str) or not dep for dep in deps)
            or len(set(deps)) != len(deps)):
        raise ValueError("decided package dependencies must be a finite unique list")
    if finishing not in deps:
        raise ValueError(f"{package_id} must directly depend on finishing package {finishing}")
    if spec["decides_next"] is not True:
        raise ValueError("decided package without a preselected successor must set decides_next=true")
    return {"id": package_id, "goal": goal.strip(), "depends_on": list(deps), "decides_next": True}


def validate_decided_candidate(plan: dict, candidate: dict) -> dict:
    active, packages = plan.get("active_package"), plan.get("packages", {})
    if plan.get("next_package") is not None:
        raise ValueError("decided transition requires next_package=null")
    if not packages.get(active, {}).get("decides_next"):
        raise ValueError("active package must decide next")
    validate_plan(plan)
    spec = _normalize_spec(candidate, finishing=active)
    activate = spec["id"]
    if activate == active:
        raise ValueError("decided package must differ from finishing package")
    existing = packages.get(activate)
    if existing is not None:
        if existing.get("status") != "planned":
            raise ValueError(f"decided package {activate} already exists with status {existing.get('status')}")
        for field in ("goal", "depends_on", "decides_next"):
            if existing.get(field) != spec[field]:
                raise ValueError(f"decided package {activate} conflicts on {field}")
    probe = json.loads(json.dumps(plan))
    if existing is None:
        probe["packages"][activate] = {"status": "planned", "depends_on": spec["depends_on"],
                                       "decides_next": True, "goal": spec["goal"]}
    problems = dependency_problems(probe, activate, finishing=active)
    if problems:
        raise ValueError("; ".join(problems))
    return spec


def decided_transition(plan: dict, *, candidate: dict, new_branch: str,
                       source_head: str, evidence: dict) -> dict:
    spec = validate_decided_candidate(plan, candidate)
    active = plan["active_package"]
    if new_branch == plan["canonical_lineage"]["working_branch"]:
        raise ValueError("next package requires a new branch")
    if not re.fullmatch(r"[0-9a-f]{40}", source_head):
        raise ValueError("source_head requires full lowercase SHA")
    if evidence.get("source_head") != source_head:
        raise ValueError("transition evidence is not bound to source_head")
    result = json.loads(json.dumps(plan))
    activate = spec["id"]
    if activate not in result["packages"]:
        result["packages"][activate] = {"status": "planned", "depends_on": spec["depends_on"],
                                        "decides_next": True, "goal": spec["goal"]}
    result["packages"][active]["status"] = "technical_pass"
    result["packages"][active]["checkpoint"] = active
    result["packages"][active].pop("evidence", None)
    result["packages"][activate]["status"] = "active"
    result["active_package"], result["next_package"] = activate, None
    lineage = result["canonical_lineage"]
    lineage["current_package_base"] = {"branch": lineage["working_branch"], "sha": source_head,
                                       "state": "verified_pr_merge_tree_checkpoint"}
    lineage["working_branch"] = new_branch
    validate_plan(result)
    return result
