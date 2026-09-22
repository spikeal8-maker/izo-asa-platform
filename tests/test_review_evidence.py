"""Structured independent review and owner-waiver regressions."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from review_evidence import (matching_structured_review, require_independent_review,  # noqa: E402
    review_decision, review_required)


def high_scope():
    return {"risk": "high", "independent_review_required": True}


def test_only_high_risk_scope_requires_review_gate():
    assert not review_required({"risk": "low"})
    assert review_required(high_scope())


def test_structured_approval_must_be_exact_and_independent():
    head = "a" * 40
    reviews = [{"id": 7, "state": "APPROVED", "commit_id": head, "user": {"login": "reviewer"}}]
    assert matching_structured_review(reviews, head, "owner") == reviews[0]
    result = review_decision(high_scope(), reviews, head, owner_login="owner")
    assert result["independent_review"] == "approved"
    assert result["independent_review_actor"] == "reviewer"
    assert not result["owner_waiver"]
    assert matching_structured_review(reviews, "b" * 40, "owner") is None


def test_owner_approve_is_not_independent():
    head = "a" * 40
    reviews = [{"id": 8, "state": "APPROVED", "commit_id": head, "user": {"login": "owner"}}]
    with pytest.raises(ValueError, match="structured independent"):
        review_decision(high_scope(), reviews, head, owner_login="owner")


def test_plain_text_marker_is_never_review_evidence():
    head = "a" * 40
    comments = [{"body": f"INDEPENDENT_REVIEW PASS source={head} reviewer=openai-chatgpt",
                 "user": {"login": "owner"}}]
    with pytest.raises(ValueError, match="plain PR comments"):
        require_independent_review(high_scope(), comments, head)


def test_explicit_owner_waiver_is_exact_and_auditable():
    head = "a" * 40
    result = review_decision(
        high_scope(), [], head, owner_login="owner", actor_login="owner",
        owner_waiver=True, independent_review_unavailable=True,
        owner_waiver_source=head, owner_waiver_reason="only owner actor is connected")
    assert result["independent_review"] == "unavailable" and result["owner_waiver"] is True
    assert result["owner_waiver_source"] == head and result["owner_waiver_reason"]
    with pytest.raises(ValueError, match="exact source SHA"):
        review_decision(
            high_scope(), [], head, owner_login="owner", actor_login="owner",
            owner_waiver=True, independent_review_unavailable=True,
            owner_waiver_source="b" * 40, owner_waiver_reason="same reason")


def test_waiver_requires_owner_actor_unavailable_assertion_and_reason():
    head = "a" * 40
    base = dict(owner_login="owner", actor_login="owner", owner_waiver=True,
                owner_waiver_source=head, owner_waiver_reason="reason")
    with pytest.raises(ValueError, match="unavailable"):
        review_decision(high_scope(), [], head, **base)
    with pytest.raises(ValueError, match="repository-owner"):
        review_decision(high_scope(), [], head, **{**base, "actor_login": "other",
            "independent_review_unavailable": True})
    with pytest.raises(ValueError, match="reason"):
        review_decision(high_scope(), [], head, **{**base, "owner_waiver_reason": "",
            "independent_review_unavailable": True})


def test_non_high_scope_needs_neither_review_nor_waiver():
    assert review_decision({"risk": "medium"}, [], "not-a-sha", owner_login="owner") == {
        "independent_review": "not_required", "owner_waiver": False}
