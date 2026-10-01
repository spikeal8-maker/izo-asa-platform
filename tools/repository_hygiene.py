"""Deterministic read-only repository hygiene and handwritten-budget gate."""
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT_LIMIT = 500 * 1024
ALLOWLIST_LIMIT = 1024 * 1024
FAIL_LIMIT = 5 * 1024 * 1024
ROOT_CONTEXT_TARGET = 4_500
ROOT_CONTEXT_HARD = 6_000
PLAN_TARGET = 4_000
PLAN_WARNING = 5_000
PLAN_HARD = 6_000
NEAR_LIMIT_RATIO = 0.80

PROD_RULES = (
    ("apps/api/izo/", {".py"}, 300, 12_000),
    ("apps/web/src/", {".ts", ".tsx", ".css"}, 300, 12_000),
)
AUX_RULES = (
    ("tests/", {".py"}, 350, 16_000),
    ("tools/", {".py"}, 350, 16_000),
    ("apps/web/e2e/", {".ts"}, 350, 16_000),
    ("apps/web/acceptance/", {".mjs"}, 350, 16_000),
    ("apps/api/migrations/", {".py"}, 350, 16_000),
)
JUNK_DIRS = {
    "__pycache__", ".venv", "node_modules", "dist", "build", "coverage",
    "playwright-report", "test-results", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
JUNK_NAMES = {".DS_Store", "Thumbs.db"}
JUNK_PATTERNS = (
    "*.pyc", "*.pyo", "*.log", "*.tmp", "*.temp", "*.bak", "*.old", "*.orig",
    "*.swp", "*~", "*.sqlite", "*.sqlite3", "*.db", "*.dump", "*.part", "*.part*",
    "*.b64", "*.base64", "*.chunk", "*-copy.*", "*_copy.*",
)
ARCHIVE_SUFFIXES = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"}
PRIVATE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
BINARY_MAGIC = (
    ("zip", b"PK\x03\x04"), ("gzip", b"\x1f\x8b"), ("sqlite", b"SQLite format 3\x00"),
    ("pdf", b"%PDF-"), ("png", b"\x89PNG\r\n\x1a\n"), ("jpeg", b"\xff\xd8\xff"),
    ("gif", b"GIF8"), ("windows-executable", b"MZ"),
)

# Exact-path exceptions only. Each entry must explain ownership and expected size.
LARGE_FILE_ALLOWLIST: dict[str, dict[str, object]] = {}


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return result.stdout


def tracked_paths(root: Path) -> list[str]:
    raw = _git(root, "ls-files", "-z")
    return sorted(p.decode("utf-8") for p in raw.split(b"\0") if p)


def default_base(root: Path) -> str | None:
    path = root / "docs" / "PLAN.json"
    if not path.is_file():
        return None
    plan = json.loads(path.read_text(encoding="utf-8"))
    return plan.get("canonical_lineage", {}).get("current_package_base", {}).get("sha")


def _changed_paths(root: Path, base: str | None) -> set[str]:
    if not base:
        return set()
    raw = _git(root, "diff", "--name-only", "--no-renames", base, "--")
    return {line for line in raw.decode("utf-8").splitlines() if line}


def _old_dimensions(root: Path, base: str, raw: str) -> tuple[int, int]:
    result = subprocess.run(["git", "show", f"{base}:{raw}"], cwd=root, capture_output=True, timeout=30)
    data = result.stdout if result.returncode == 0 else b""
    return len(data), len(data.decode("utf-8", "replace").splitlines())


def _size(root: Path, raw: str) -> int:
    path = root / raw
    return path.stat().st_size if path.is_file() else 0


def _handwritten_rule(raw: str):
    path = PurePosixPath(raw)
    if ".generated." in path.name:
        return None
    for prefix, suffixes, max_lines, max_bytes in (*PROD_RULES, *AUX_RULES):
        if raw.startswith(prefix) and path.suffix in suffixes:
            return max_lines, max_bytes
    return None


def _junk_reason(raw: str) -> str | None:
    path = PurePosixPath(raw)
    if any(part in JUNK_DIRS for part in path.parts):
        return "tracked junk/runtime directory"
    if path.name in JUNK_NAMES or any(fnmatch.fnmatchcase(path.name, pattern) for pattern in JUNK_PATTERNS):
        return "tracked junk/temporary artifact"
    if path.name == ".env" or (path.name.startswith(".env.") and path.name not in {".env.example", ".env.sample"}):
        return "tracked private runtime artifact"
    if path.suffix.lower() in PRIVATE_SUFFIXES:
        return "tracked private key/container artifact"
    return None


def _binary_reason(path: Path, raw: str) -> str | None:
    if path.suffix.lower() in ARCHIVE_SUFFIXES:
        return "unexpected tracked archive"
    head = path.read_bytes()[:8192]
    for kind, magic in BINARY_MAGIC:
        if head.startswith(magic):
            return f"unexpected tracked binary ({kind})"
    if b"\x00" in head:
        return "unexpected tracked binary (NUL byte)"
    return None


def _allow_entry(raw: str, size: int, allowlist: dict[str, dict[str, object]]) -> tuple[bool, str]:
    entry = allowlist.get(raw)
    if entry is None:
        return False, "exact allowlist entry required"
    required = {"reason", "owner", "kind", "maximum_expected_size"}
    if set(entry) != required:
        return False, "allowlist metadata must be reason/owner/kind/maximum_expected_size"
    if entry["kind"] not in {"generated", "manual"}:
        return False, "allowlist kind must be generated or manual"
    if not isinstance(entry["reason"], str) or not entry["reason"].strip():
        return False, "allowlist reason is empty"
    if not isinstance(entry["owner"], str) or not entry["owner"].strip():
        return False, "allowlist owner is empty"
    maximum = entry["maximum_expected_size"]
    if type(maximum) is not int or maximum <= 0:
        return False, "allowlist maximum_expected_size is invalid"
    if size > maximum:
        return False, f"size {size} exceeds allowlisted maximum {maximum}"
    return True, ""


def scan(root: Path = ROOT, *, base: str | None = None,
         allowlist: dict[str, dict[str, object]] | None = None) -> dict:
    allowlist = LARGE_FILE_ALLOWLIST if allowlist is None else allowlist
    paths = tracked_paths(root)
    base = default_base(root) if base is None else base
    changed = _changed_paths(root, base)
    failures: list[tuple[str, str]] = []
    reports: list[tuple[str, str]] = []
    near_limit: list[dict[str, object]] = []
    total_bytes = 0
    over_500 = over_1m = over_5m = 0

    for raw in paths:
        path = root / raw
        size = path.stat().st_size
        total_bytes += size
        if size > REPORT_LIMIT:
            over_500 += 1
            reports.append((raw, f"tracked file is >500 KB ({size} bytes)"))
        if size > ALLOWLIST_LIMIT:
            over_1m += 1
        if size > FAIL_LIMIT:
            over_5m += 1
            failures.append((raw, f"tracked file exceeds 5 MB hard default ({size} bytes)"))
        elif size > ALLOWLIST_LIMIT:
            allowed, reason = _allow_entry(raw, size, allowlist)
            if not allowed:
                failures.append((raw, f"tracked file exceeds 1 MB: {reason}"))

        junk = _junk_reason(raw)
        if junk:
            failures.append((raw, junk))

        binary = _binary_reason(path, raw)
        if binary:
            allowed, reason = _allow_entry(raw, size, allowlist)
            if not allowed:
                failures.append((raw, f"{binary}: {reason}"))

        rule = _handwritten_rule(raw)
        if not rule:
            continue
        max_lines, max_bytes = rule
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append((raw, "handwritten source is not UTF-8 text"))
            continue
        lines = len(text.splitlines())
        if size > max_bytes:
            failures.append((raw, f"handwritten hard byte limit {size}>{max_bytes}"))
        if lines > max_lines:
            failures.append((raw, f"handwritten hard line limit {lines}>{max_lines}"))
        is_near = size > int(max_bytes * NEAR_LIMIT_RATIO) or lines > int(max_lines * NEAR_LIMIT_RATIO)
        if is_near:
            entry = {
                "path": raw,
                "bytes": size,
                "lines": lines,
                "max_bytes": max_bytes,
                "max_lines": max_lines,
            }
            near_limit.append(entry)
        if base and raw in changed:
            old_size, old_lines = _old_dimensions(root, base, raw)
            old_near = old_size > int(max_bytes * NEAR_LIMIT_RATIO) or old_lines > int(max_lines * NEAR_LIMIT_RATIO)
            if (is_near or old_near) and (not old_size or size > old_size or lines > old_lines):
                failures.append((raw, f"near-limit handwritten file grew: bytes {old_size}->{size}, "
                                      f"lines {old_lines}->{lines}; split responsibility"))

    root_context_bytes = _size(root, "AGENTS.md") + _size(root, "docs/CURRENT.md")
    live_plan_bytes = _size(root, "docs/PLAN.json")
    return {
        "tracked_files": len(paths),
        "tracked_bytes": total_bytes,
        "files_over_500kb": over_500,
        "files_over_1mb": over_1m,
        "files_over_5mb": over_5m,
        "tracked_junk": sum(1 for _, reason in failures if "junk" in reason),
        "root_context_bytes": root_context_bytes,
        "root_context_target": ROOT_CONTEXT_TARGET,
        "root_context_hard_limit": ROOT_CONTEXT_HARD,
        "live_plan_bytes": live_plan_bytes,
        "live_plan_target": PLAN_TARGET,
        "live_plan_warning": PLAN_WARNING,
        "live_plan_hard_limit": PLAN_HARD,
        "near_limit_handwritten": near_limit,
        "changed_near_limit_handwritten": [item for item in near_limit if item["path"] in changed],
        "failures": sorted(set(failures)),
        "reports": sorted(set(reports)),
        "base": base,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = scan(base=args.base)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print("FAIL")
        print(f"<repository>\tchecker error: {type(exc).__name__}: {exc}")
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key in (
            "tracked_files", "tracked_bytes", "files_over_500kb", "files_over_1mb",
            "files_over_5mb", "tracked_junk", "root_context_bytes", "root_context_target",
            "root_context_hard_limit", "live_plan_bytes", "live_plan_target",
            "live_plan_warning", "live_plan_hard_limit",
        ):
            print(f"{key.upper()} {result[key]}")
        for item in result["near_limit_handwritten"]:
            print(f"NEAR_LIMIT\t{item['path']}\t{item['bytes']} bytes\t{item['lines']} lines")
        for item in result["changed_near_limit_handwritten"]:
            print(f"CHANGED_NEAR_LIMIT\t{item['path']}\t{item['bytes']} bytes\t{item['lines']} lines")
        for raw, reason in result["reports"]:
            print(f"REPORT\t{raw}\t{reason}")
        if result["failures"]:
            print("FAIL")
            for raw, reason in result["failures"]:
                print(f"{raw}\t{reason}")
        else:
            print("PASS")
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
