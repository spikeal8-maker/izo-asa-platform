"""Read-only scope check and conservative test plan. Does NOT execute tests."""
from __future__ import annotations
import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SENSITIVE = ("AGENTS.md", "**/AGENTS.md", ".github/*", "infra/*", "compose*", "LICENSE*", "requirements*", "tools/*", "apps/api/migrations/*", "**/package*.json")


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Git check failed: verify the base commit and full checkout")
    return result.stdout


def changed_paths(root: Path, base: str) -> list[str]:
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("Base must be the approved full commit SHA")
    git(root, "cat-file", "-e", f"{base}^{{commit}}")
    git(root, "merge-base", "--is-ancestor", base, "HEAD")
    # --no-renames checks BOTH old/deleted and new paths. Includes staged and
    # unstaged tracked files; untracked, non-ignored files are added separately.
    raw = git(root, "diff", "--no-renames", "--name-only", "-z", base, "--")
    raw += git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(set(p.decode("utf-8") for p in raw.split(b"\0") if p))


def matches(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def inspect(paths: list[str], scope: dict) -> dict:
    allowed = scope.get("allowed", [])
    reviewed = scope.get("sensitive_approved", [])
    limit = scope.get("max_files")
    if not (isinstance(allowed, list) and allowed and all(isinstance(p, str) and p for p in allowed)):
        raise ValueError("Scope requires explicit allowed path patterns")
    if not isinstance(reviewed, list) or not all(isinstance(p, str) for p in reviewed):
        raise ValueError("Invalid sensitive_approved")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("max_files must be a finite integer between 1 and 100")
    invalid = [p for p in paths if not p or p.startswith("/") or "\\" in p or ".." in PurePosixPath(p).parts]
    outside = [p for p in paths if not matches(p, allowed)]
    sensitive = [p for p in paths if matches(p, SENSITIVE) and not matches(p, reviewed)]
    groups = set()
    for p in paths:
        if p.startswith("apps/web/"):
            groups.add("web")
        elif p.startswith(("tests/", "tools/", "apps/api/")):
            groups.add("python")
        elif not (p.endswith(".md") or p.startswith("tools/scopes/")):
            groups.add("full")
    commands = []
    if "web" in groups:
        commands += ["cd apps/web && npm run build", "cd apps/web && npx playwright test --project=phone --project=laptop"]
    if "python" in groups:
        commands += ["python -m pytest", "python tools/export_contracts.py --check"]
    if "full" in groups:
        commands += ["Unmapped area: use the full existing CI; do not skip unknown checks"]
    if not groups:
        commands += ["Review document links, requirements vs implementation, and the exact diff"]
    return {"scope_ok": not (invalid or outside or sensitive or len(paths) > limit),
            "changed_count": len(paths), "max_files": limit, "paths": paths,
            "invalid": invalid, "outside_scope": outside, "unapproved_sensitive": sensitive,
            "recommended_checks": commands, "tests_executed": False,
            "full_ci_required_before_acceptance": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--scope", required=True, type=Path)
    args = parser.parse_args()
    try:
        scope = json.loads(args.scope.read_text(encoding="utf-8"))
        report = inspect(changed_paths(ROOT, args.base), scope)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["scope_ok"] else 1
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"SCOPE CHECK NOT COMPLETED: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
