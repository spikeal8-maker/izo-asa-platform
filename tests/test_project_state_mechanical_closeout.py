"""Mechanical state-only closeout proof stays exact and fail-closed."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from project_state_mechanical_closeout import mechanical_state_only_closeout
from project_state_model import (
    load_checkpoints, load_plan, render_current, serialize_checkpoints, validate_plan,
)
from project_state_registry import serialize_packages, serialize_plan


def fixture():
    source, head, merge = "8" * 40, "9" * 40, "a" * 40
    plan = load_plan()
    package = plan["active_package"]
    plan["packages"][package]["status"] = "active"
    plan["packages"][package].pop("checkpoint", None)
    plan["next_package"] = None
    validate_plan(plan)

    checkpoints = json.loads(json.dumps(load_checkpoints()))
    checkpoints.setdefault("checkpoints", {}).pop(package, None)
    checkpoint = {
        "type": "pr_merge_tree",
        "source_head": source,
        "verified_pr": 77,
        "base_head": "7" * 40,
        "tested_merge_tree": "6" * 40,
        "workflows": {
            "Foundation CI": 1,
            "Dependency Security": 2,
            "Review Source": 3,
        },
        "independent_review": "not_required",
        "owner_waiver": False,
    }

    expected = json.loads(json.dumps(plan))
    expected["packages"][package]["status"] = "complete"
    expected["packages"][package]["checkpoint"] = package
    expected_checkpoints = json.loads(json.dumps(checkpoints))
    expected_checkpoints["checkpoints"][package] = checkpoint

    source_files = {
        "docs/PLAN.json": serialize_plan(plan),
        "docs/PACKAGES.json": serialize_packages(plan),
        "docs/CHECKPOINTS.json": serialize_checkpoints(checkpoints),
    }
    head_files = {
        "docs/PLAN.json": serialize_plan(expected),
        "docs/PACKAGES.json": serialize_packages(expected),
        "docs/CURRENT.md": render_current(expected),
        "docs/CHECKPOINTS.json": serialize_checkpoints(expected_checkpoints),
    }
    rows = [
        {"filename": name, "status": "modified"}
        for name in ("docs/CHECKPOINTS.json", "docs/CURRENT.md", "docs/PACKAGES.json")
    ]
    return source, head, merge, package, checkpoint, source_files, head_files, rows


def test_exact_generated_state_is_mechanical_closeout():
    source, head, merge, package, checkpoint, source_files, head_files, rows = fixture()

    def git_fn(*args, root):
        sha, filename = args[1].split(":", 1)
        return (source_files if sha == source else head_files)[filename]

    def gh_fn(args, root):
        assert "/files?" in " ".join(args)
        return [rows]

    assert mechanical_state_only_closeout(
        77, head, source, package, checkpoint, "owner/repo",
        root=ROOT, git_fn=git_fn, gh_fn=gh_fn, merge_head=merge,
    )


def test_runtime_file_or_tampered_state_fails_closed():
    source, head, merge, package, checkpoint, source_files, head_files, rows = fixture()

    def git_fn(*args, root):
        sha, filename = args[1].split(":", 1)
        return (source_files if sha == source else head_files)[filename]

    def gh_fn(args, root):
        return [rows]

    rows.append({"filename": "tools/project_state.py", "status": "modified"})
    assert not mechanical_state_only_closeout(
        77, head, source, package, checkpoint, "owner/repo",
        root=ROOT, git_fn=git_fn, gh_fn=gh_fn, merge_head=merge,
    )
    rows.pop()

    head_files["docs/CURRENT.md"] += "tampered\n"
    assert not mechanical_state_only_closeout(
        77, head, source, package, checkpoint, "owner/repo",
        root=ROOT, git_fn=git_fn, gh_fn=gh_fn, merge_head=merge,
    )

    head_files["docs/CURRENT.md"] = head_files["docs/CURRENT.md"].removesuffix("tampered\n")
    merge_files = dict(head_files)
    merge_files["docs/CURRENT.md"] += "concurrent-main-change\n"

    def merge_git_fn(*args, root):
        sha, filename = args[1].split(":", 1)
        if sha == source:
            return source_files[filename]
        if sha == merge:
            return merge_files[filename]
        return head_files[filename]

    assert not mechanical_state_only_closeout(
        77, head, source, package, checkpoint, "owner/repo",
        root=ROOT, git_fn=merge_git_fn, gh_fn=gh_fn, merge_head=merge,
    )
