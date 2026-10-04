"""Fail closed when a pull-request diff is not bound to one reviewed scope."""
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import subprocess
import sys

from check_change import changed_paths, inspect, validate_base

ROOT = Path(__file__).resolve().parents[1]
STATE_ONLY = {
    "docs/PLAN.json",
    "docs/PACKAGES.json",
    "docs/CURRENT.md",
    "docs/CHECKPOINTS.json",
}
DEPENDABOT_PATTERNS = (
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "requirements.in",
    "requirements-dev.txt",
    "requirements.lock",
    "infra/**/Dockerfile",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _git_text(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="strict", timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _local_mechanical_closeout(paths: list[str], base: str, *, root: Path) -> bool:
    from project_state_mechanical_closeout import mechanical_state_only_closeout

    head = _git_text(root, "rev-parse", "HEAD")
    plan = json.loads(_git_text(root, "show", f"{base}:docs/PLAN.json"))
    package = plan.get("active_package")
    if not isinstance(package, str) or not package:
        return False
    checkpoints = json.loads(_git_text(root, "show", f"{head}:docs/CHECKPOINTS.json"))
    checkpoint = checkpoints.get("checkpoints", {}).get(package)
    if not isinstance(checkpoint, dict):
        return False
    rows = [[{"filename": path, "status": "modified"} for path in paths]]
    return mechanical_state_only_closeout(
        0, head, base, package, checkpoint, "local/repo", root=root,
        git_fn=lambda *args, root=root: _git_text(root, *args),
        gh_fn=lambda args, root=root: rows,
    )


def select_scope(paths: list[str], *, root: Path = ROOT) -> Path | None:
    changed = [
        root / path for path in paths
        if path.startswith("tools/scopes/") and path.endswith(".json")
    ]
    if len(changed) > 1:
        raise ValueError("pull request changes more than one scope manifest")
    return changed[0] if changed else None


def evaluate(base: str, actor: str, *, root: Path = ROOT) -> dict:
    paths = changed_paths(root, base)
    if not paths:
        return {"scope_ok": True, "mode": "empty", "paths": []}
    if set(paths).issubset(STATE_ONLY):
        if not _local_mechanical_closeout(paths, base, root=root):
            raise ValueError("state-only pull request is not an exact mechanical closeout")
        return {"scope_ok": True, "mode": "state_only", "paths": paths}

    scope_path = select_scope(paths, root=root)
    if scope_path is not None:
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        validate_base(base, scope)
        report = inspect(paths, scope)
        report["mode"] = "manifest"
        report["scope"] = scope_path.relative_to(root).as_posix()
        return report

    if actor.startswith("dependabot"):
        bad = [path for path in paths if not _matches_any(path, DEPENDABOT_PATTERNS)]
        return {
            "scope_ok": not bad and len(paths) <= 8,
            "mode": "dependabot",
            "paths": paths,
            "outside_scope": bad,
        }

    raise ValueError(
        "non-state pull request requires exactly one changed tools/scopes/*.json manifest"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--actor", default="")
    args = parser.parse_args()
    try:
        report = evaluate(args.base, args.actor)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("scope_ok") else 1
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"CI SCOPE ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
