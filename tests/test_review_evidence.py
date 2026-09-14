"""Independent-review evidence must be explicit and bound to the frozen source."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from review_evidence import matching_review, require_independent_review, review_required  # noqa: E402


def high_scope():
    return {"risk": "high", "independent_review_required": True}


def test_only_high_risk_scope_requires_independent_review():
    assert not review_required({"risk": "low"})
    assert not review_required({"risk": "medium"})
    assert review_required(high_scope())


def test_review_marker_is_bound_to_exact_source_sha():
    head = "a" * 40
    comments = [{"body": f"INDEPENDENT_REVIEW PASS source={head} reviewer=security-agent"}]
    assert matching_review(comments, head) == comments[0]
    require_independent_review(high_scope(), comments, head)
    with pytest.raises(ValueError, match="high-risk package"):
        require_independent_review(high_scope(), comments, "b" * 40)


def test_review_marker_requires_explicit_reviewer_and_pass():
    head = "a" * 40
    invalid = [
        {"body": f"INDEPENDENT_REVIEW FAIL source={head} reviewer=reviewer"},
        {"body": f"INDEPENDENT_REVIEW PASS source={head}"},
        {"body": "looks good"},
    ]
    with pytest.raises(ValueError, match="INDEPENDENT_REVIEW PASS"):
        require_independent_review(high_scope(), invalid, head)


def test_non_high_scope_does_not_need_comment():
    require_independent_review({"risk": "medium"}, [], "not-a-sha")


def test_begin_next_rejects_high_risk_before_creating_branch(monkeypatch):
    import project_state as state
    source = json.loads((ROOT / "docs/PLAN.json").read_text(encoding="utf-8"))
    head = "a" * 40
    branch_events = []

    def fake_git(*args, root=ROOT):
        if args == ("status", "--porcelain"):
            return ""
        if args == ("branch", "--show-current"):
            return source["canonical_lineage"]["working_branch"]
        if args == ("rev-parse", "HEAD"):
            return head
        if args[:2] == ("switch", "-c"):
            branch_events.append(args)
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(state, "git", fake_git)
    monkeypatch.setattr(state, "active_scope", lambda *a, **k: high_scope())
    monkeypatch.setattr(state, "repo_slug", lambda *a, **k: "owner/repo")
    monkeypatch.setattr(state, "gh_json", lambda *a, **k: [])
    with pytest.raises(ValueError, match="high-risk package"):
        state.begin_next(source, branch="next/test", activate="CATALOG-002", next_id=None,
                         verified_pr=99, root=ROOT)
    assert branch_events == []
