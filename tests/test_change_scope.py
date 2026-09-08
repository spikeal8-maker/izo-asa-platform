"""Executable scope guard regressions. Temporary Git repositories, no network."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("change_guard", ROOT / "tools/check_change.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
SCOPE = {"allowed": ["apps/web/*"], "sensitive_approved": [], "max_files": 3}


def test_normal_ui_is_local():
    result = guard.inspect(["apps/web/src/features/studio/Studio.tsx"], SCOPE)
    assert result["scope_ok"] and not result["tests_executed"]
    assert result["full_ci_required_before_acceptance"]


@pytest.mark.parametrize("path", ["apps/api/izo/app.py", "infra/api.Dockerfile", "LICENSE", ".github/workflows/ci.yml", "../secret", "/outside", "apps\\web\\x"])
def test_unrelated_or_invalid_changes_rejected(path):
    assert not guard.inspect([path], SCOPE)["scope_ok"]


def test_sensitive_within_allowed_still_needs_explicit_scope():
    assert not guard.inspect(["apps/web/package.json"], SCOPE)["scope_ok"]
    scope = dict(SCOPE, sensitive_approved=["apps/web/package.json"])
    assert guard.inspect(["apps/web/package.json"], scope)["scope_ok"]


def test_file_budget_cannot_be_silently_exceeded():
    assert not guard.inspect([f"apps/web/{i}.tsx" for i in range(4)], SCOPE)["scope_ok"]


@pytest.mark.parametrize("limit", [0, -1, None, True, 101])
def test_invalid_limits_fail_closed(limit):
    with pytest.raises(ValueError):
        guard.inspect([], dict(SCOPE, max_files=limit))


def test_unknown_area_does_not_skip_tests():
    result = guard.inspect(["new-area/file.rs"], {"allowed": ["new-area/*"], "max_files": 2})
    assert "full existing CI" in result["recommended_checks"][0]


def test_tracked_untracked_rename_and_deletion_are_all_inspected(tmp_path):
    def run(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path)
    run("init", "-q")
    run("config", "user.name", "Fixture")
    run("config", "user.email", "fixture@example.invalid")
    (tmp_path / "old.txt").write_text("old", encoding="utf-8")
    (tmp_path / "deleted.txt").write_text("delete", encoding="utf-8")
    run("add", ".")
    run("commit", "-qm", "baseline")
    base = run("rev-parse", "HEAD").decode().strip()
    run("mv", "old.txt", "new name.txt")
    (tmp_path / "deleted.txt").unlink()
    (tmp_path / "untracked.txt").write_text("new", encoding="utf-8")
    assert guard.changed_paths(tmp_path, base) == ["deleted.txt", "new name.txt", "old.txt", "untracked.txt"]
    with pytest.raises(ValueError):
        guard.changed_paths(tmp_path, "main")


def test_scope_manifest_is_explicit_about_non_goals():
    scope = json.loads((ROOT / "tools/scopes/ux-001.json").read_text())
    assert scope["max_files"] == 32
    assert not guard.inspect(["apps/api/izo/app.py"], scope)["scope_ok"]
    assert not guard.inspect([".github/workflows/ci.yml"], scope)["scope_ok"]
