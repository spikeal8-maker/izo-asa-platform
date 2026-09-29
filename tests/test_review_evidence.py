"""Structured independent review and owner-waiver regressions."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from review_evidence import (matching_structured_review, require_independent_review,  # noqa: E402
    review_decision, review_required)
from project_state_evidence import validate_pr_evidence  # noqa: E402


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


def test_latest_review_verdict_wins_over_historical_approval():
    head = "a" * 40
    reviews = [
        {"id": 1, "state": "APPROVED", "commit_id": head,
         "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}},
        {"id": 2, "state": "CHANGES_REQUESTED", "commit_id": head,
         "submitted_at": "2026-09-22T10:05:00Z", "user": {"login": "reviewer"}},
    ]
    with pytest.raises(ValueError, match="changes requested"):
        review_decision(high_scope(), reviews, head, owner_login="owner")


def test_later_approval_supersedes_changes_requested_on_exact_head():
    head = "a" * 40
    reviews = [
        {"id": 1, "state": "CHANGES_REQUESTED", "commit_id": head,
         "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}},
        {"id": 2, "state": "APPROVED", "commit_id": head,
         "submitted_at": "2026-09-22T10:05:00Z", "user": {"login": "reviewer"}},
    ]
    result = review_decision(high_scope(), reviews, head, owner_login="owner")
    assert result["independent_review"] == "approved"
    assert result["independent_review_id"] == 2


@pytest.mark.parametrize("review", [
    {"id": 1, "state": "DISMISSED", "commit_id": "a" * 40,
     "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}},
    {"id": 2, "state": "APPROVED", "commit_id": "b" * 40,
     "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}},
    {"id": 3, "state": "APPROVED", "commit_id": "a" * 40,
     "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "owner"}},
    {"id": 4, "state": "COMMENTED", "commit_id": "a" * 40,
     "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}},
])
def test_dismissed_wrong_sha_self_and_comment_are_not_independent_approval(review):
    with pytest.raises(ValueError, match="structured independent"):
        review_decision(high_scope(), [review], "a" * 40, owner_login="owner")


def test_owner_waiver_does_not_mask_current_changes_requested():
    head = "a" * 40
    reviews = [
        {"id": 1, "state": "APPROVED", "commit_id": head,
         "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}},
        {"id": 2, "state": "CHANGES_REQUESTED", "commit_id": head,
         "submitted_at": "2026-09-22T10:05:00Z", "user": {"login": "reviewer"}},
    ]
    with pytest.raises(ValueError, match="changes requested"):
        review_decision(
            high_scope(), reviews, head, owner_login="owner", actor_login="owner",
            owner_waiver=True, independent_review_unavailable=True,
            owner_waiver_source=head, owner_waiver_reason="only owner actor connected")


def test_review_fetch_keeps_second_page_latest_verdict(monkeypatch):
    import project_state_evidence as evidence_module
    head = "a" * 40
    page1 = [{"id": 1, "state": "CHANGES_REQUESTED", "commit_id": head,
              "submitted_at": "2026-09-22T10:00:00Z", "user": {"login": "reviewer"}}]
    page2 = [{"id": 2, "state": "APPROVED", "commit_id": head,
              "submitted_at": "2026-09-22T10:05:00Z", "user": {"login": "reviewer"}}]

    monkeypatch.setattr(evidence_module, "repo_slug", lambda root=None: "owner/repo")

    def fake_gh(args, root=None):
        joined = " ".join(args)
        if "/pulls/99/reviews" in joined:
            return [page1, page2] if "--paginate" in args else page1
        raise AssertionError(args)

    monkeypatch.setattr(evidence_module, "gh_json", fake_gh)
    result = evidence_module.fetch_review_evidence(high_scope(), 99, head)
    assert result["independent_review"] == "approved"
    assert result["independent_review_id"] == 2

def _runs_for_freshness(head, foundation_rows):
    other = [
        {"name": "Dependency Security", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 50,
         "runAttempt": 1, "prNumbers": [99]},
        {"name": "Review Source", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 60,
         "runAttempt": 1, "prNumbers": [99]},
    ]
    return [*foundation_rows, *other]


def _validate_runs(runs, head="a" * 40):
    return validate_pr_evidence(
        pr={"headRefOid": head, "baseRefOid": "b" * 40, "state": "OPEN"},
        runs=runs, merge_sha="c" * 40,
        merge_commit={"parents": [{"sha": "b" * 40}, {"sha": head}]},
        expected_head=head, pr_number=99, foundation_tree="c" * 40)


def test_latest_required_ci_failure_blocks_old_success():
    head = "a" * 40
    rows = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 10,
         "runAttempt": 1, "prNumbers": [99]},
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "failure", "databaseId": 11,
         "runAttempt": 1, "prNumbers": [99]},
    ]
    with pytest.raises(ValueError, match="latest.*Foundation CI"):
        _validate_runs(_runs_for_freshness(head, rows), head)


def test_latest_required_ci_in_progress_blocks_old_success():
    head = "a" * 40
    rows = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 10,
         "runAttempt": 1, "prNumbers": [99]},
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "in_progress", "conclusion": None, "databaseId": 11,
         "runAttempt": 1, "prNumbers": [99]},
    ]
    with pytest.raises(ValueError, match="latest.*Foundation CI"):
        _validate_runs(_runs_for_freshness(head, rows), head)


def test_new_success_supersedes_old_failure():
    head = "a" * 40
    rows = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "failure", "databaseId": 10,
         "runAttempt": 1, "prNumbers": [99]},
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 11,
         "runAttempt": 2, "prNumbers": [99]},
    ]
    result = _validate_runs(_runs_for_freshness(head, rows), head)
    assert result["workflows"]["Foundation CI"] == 11


def test_ci_from_other_pr_is_not_evidence():
    head = "a" * 40
    rows = [
        {"name": "Foundation CI", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 11,
         "runAttempt": 1, "prNumbers": [100]},
        {"name": "Dependency Security", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 12,
         "runAttempt": 1, "prNumbers": [100]},
        {"name": "Review Source", "headSha": head, "event": "pull_request",
         "status": "completed", "conclusion": "success", "databaseId": 13,
         "runAttempt": 1, "prNumbers": [100]},
    ]
    with pytest.raises(ValueError, match="PR #99"):
        _validate_runs(rows, head)

