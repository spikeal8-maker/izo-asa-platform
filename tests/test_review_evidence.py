"""Independent-review evidence must be explicit and bound to the frozen source."""
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
