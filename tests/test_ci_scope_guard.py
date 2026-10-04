"""PR scope selection is deterministic and fail-closed."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ci_scope_guard as guard


def test_state_only_diff_needs_no_separate_scope(monkeypatch):
    monkeypatch.setattr(guard, "changed_paths", lambda root, base: [
        "docs/CURRENT.md", "docs/PACKAGES.json",
    ])
    monkeypatch.setattr(guard, "_local_mechanical_closeout", lambda *a, **k: True)
    result = guard.evaluate("a" * 40, "owner", root=ROOT)
    assert result["scope_ok"] is True
    assert result["mode"] == "state_only"


def test_state_only_diff_that_is_not_mechanical_fails(monkeypatch):
    monkeypatch.setattr(guard, "changed_paths", lambda root, base: ["docs/CURRENT.md"])
    monkeypatch.setattr(guard, "_local_mechanical_closeout", lambda *a, **k: False)
    with pytest.raises(ValueError, match="not an exact mechanical closeout"):
        guard.evaluate("a" * 40, "owner", root=ROOT)


def test_ordinary_pr_without_changed_scope_fails(monkeypatch):
    monkeypatch.setattr(guard, "changed_paths", lambda root, base: [
        "apps/web/src/shell/ChatPage.tsx",
    ])
    with pytest.raises(ValueError, match="requires exactly one changed"):
        guard.evaluate("a" * 40, "owner", root=ROOT)


def test_manifest_is_used_for_ordinary_pr(tmp_path, monkeypatch):
    scope = tmp_path / "tools" / "scopes" / "demo.json"
    scope.parent.mkdir(parents=True)
    scope.write_text(json.dumps({
        "package_id": "DEMO",
        "base": "a" * 40,
        "scope_class": "tiny",
        "risk": "medium",
        "independent_review_required": False,
        "max_files": 2,
        "allowed": ["tools/scopes/demo.json", "docs/UX.md"],
        "sensitive_approved": ["tools/scopes/demo.json"],
    }), encoding="utf-8")
    monkeypatch.setattr(guard, "changed_paths", lambda root, base: [
        "docs/UX.md", "tools/scopes/demo.json",
    ])
    result = guard.evaluate("a" * 40, "owner", root=tmp_path)
    assert result["scope_ok"] is True
    assert result["scope"] == "tools/scopes/demo.json"


def test_dependabot_is_bounded_to_dependency_files(monkeypatch):
    monkeypatch.setattr(guard, "changed_paths", lambda root, base: [
        "apps/web/package.json", "apps/web/package-lock.json",
    ])
    assert guard.evaluate("a" * 40, "dependabot[bot]", root=ROOT)["scope_ok"] is True
    monkeypatch.setattr(guard, "changed_paths", lambda root, base: [
        "apps/web/package-lock.json", "apps/web/src/shell/ChatPage.tsx",
    ])
    result = guard.evaluate("a" * 40, "dependabot[bot]", root=ROOT)
    assert result["scope_ok"] is False
    assert result["outside_scope"] == ["apps/web/src/shell/ChatPage.tsx"]
