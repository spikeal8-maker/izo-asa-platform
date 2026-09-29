from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import repository_hygiene as hygiene


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Hygiene Fixture")
    git(tmp_path, "config", "user.email", "hygiene@example.invalid")
    return tmp_path


def commit_all(root: Path, message: str = "fixture") -> str:
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def reasons(result: dict) -> str:
    return "\n".join(f"{path}: {reason}" for path, reason in result["failures"])


def test_current_repository_is_clean():
    result = hygiene.scan(ROOT)
    assert not result["failures"], reasons(result)
    assert result["files_over_1mb"] == 0
    assert result["files_over_5mb"] == 0


def test_clean_repo_passes(tmp_path):
    root = repo(tmp_path)
    (root / "README.md").write_text("clean\n", encoding="utf-8")
    commit_all(root)
    assert not hygiene.scan(root)["failures"]


@pytest.mark.parametrize("raw", [
    "runtime/app.log",
    "runtime/state.sqlite",
    "node_modules/pkg/index.js",
    "uploads/file.part",
    ".env",
])
def test_tracked_junk_fails(tmp_path, raw):
    root = repo(tmp_path)
    path = root / raw
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("tracked junk", encoding="utf-8")
    commit_all(root)
    result = hygiene.scan(root)
    assert raw in reasons(result)


def test_unexpected_large_file_over_one_mb_fails(tmp_path):
    root = repo(tmp_path)
    path = root / "packages/contracts/large.generated.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (hygiene.ALLOWLIST_LIMIT + 1))
    commit_all(root)
    result = hygiene.scan(root)
    assert "exact allowlist entry required" in reasons(result)


def test_exact_allowed_generated_large_file_passes(tmp_path):
    root = repo(tmp_path)
    raw = "packages/contracts/large.generated.json"
    path = root / raw
    path.parent.mkdir(parents=True)
    size = hygiene.ALLOWLIST_LIMIT + 1
    path.write_bytes(b"x" * size)
    commit_all(root)
    allowlist = {
        raw: {
            "reason": "generated contract fixture",
            "owner": "contracts",
            "kind": "generated",
            "maximum_expected_size": size + 1024,
        }
    }
    result = hygiene.scan(root, allowlist=allowlist)
    assert not result["failures"], reasons(result)


def test_file_over_five_mb_fails_even_without_other_junk(tmp_path):
    root = repo(tmp_path)
    path = root / "assets/oversize.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (hygiene.FAIL_LIMIT + 1))
    commit_all(root)
    result = hygiene.scan(root)
    assert "exceeds 5 MB hard default" in reasons(result)


def test_unexpected_binary_archive_fails(tmp_path):
    root = repo(tmp_path)
    path = root / "artifact.zip"
    path.write_bytes(b"PK\x03\x04fixture")
    commit_all(root)
    result = hygiene.scan(root)
    assert "unexpected tracked archive" in reasons(result)


def test_near_limit_source_growth_fails(tmp_path):
    root = repo(tmp_path)
    path = root / "apps/api/izo/near_limit.py"
    path.parent.mkdir(parents=True)
    body = "# " + ("x" * 47) + "\n"
    path.write_text(body * 200, encoding="utf-8")
    base = commit_all(root, "base")
    assert path.stat().st_size > int(12_000 * 0.80)
    path.write_text(path.read_text(encoding="utf-8") + "# grew\n", encoding="utf-8")
    commit_all(root, "growth")
    result = hygiene.scan(root, base=base)
    assert "near-limit handwritten file grew" in reasons(result)
