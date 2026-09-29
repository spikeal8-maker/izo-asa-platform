"""Structured review evidence and explicit owner-waiver semantics."""
from __future__ import annotations
import re

SHA_RE = re.compile(r"[0-9a-f]{40}")
DECISIVE_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


def review_required(scope: dict) -> bool:
    return scope.get("risk") == "high" or scope.get("independent_review_required") is True


def current_reviewer_verdicts(reviews: list[dict], source_sha: str,
                              owner_login: str) -> dict[str, dict]:
    if not SHA_RE.fullmatch(source_sha):
        return {}
    latest: dict[str, tuple[tuple[str, int, int], dict]] = {}
    for position, review in enumerate(reviews):
        login = (review.get("user") or {}).get("login")
        state = str(review.get("state", "")).upper()
        if (review.get("commit_id") != source_sha or state not in DECISIVE_STATES
                or not isinstance(login, str) or not login or login == owner_login):
            continue
        try:
            review_id = int(review.get("id") or 0)
        except (TypeError, ValueError):
            review_id = 0
        order = (str(review.get("submitted_at") or ""), review_id, position)
        if login not in latest or order > latest[login][0]:
            latest[login] = (order, review)
    return {login: item[1] for login, item in latest.items()}


def matching_structured_review(reviews: list[dict], source_sha: str,
                               owner_login: str) -> dict | None:
    return next((review for review in current_reviewer_verdicts(
        reviews, source_sha, owner_login).values()
        if str(review.get("state", "")).upper() == "APPROVED"), None)


def review_decision(scope: dict, reviews: list[dict], source_sha: str, *, owner_login: str,
                    actor_login: str | None = None, owner_waiver: bool = False,
                    independent_review_unavailable: bool = False,
                    owner_waiver_source: str | None = None,
                    owner_waiver_reason: str | None = None) -> dict:
    if not review_required(scope):
        return {"independent_review": "not_required", "owner_waiver": False}
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("review evidence requires an exact source SHA")
    verdicts = current_reviewer_verdicts(reviews, source_sha, owner_login)
    blocked = [review for review in verdicts.values()
               if str(review.get("state", "")).upper() == "CHANGES_REQUESTED"]
    if blocked:
        actors = sorted({review["user"]["login"] for review in blocked})
        raise ValueError(f"structured independent review has current changes requested: {actors}")
    approved = next((review for review in verdicts.values()
                     if str(review.get("state", "")).upper() == "APPROVED"), None)
    if approved is not None:
        return {"independent_review": "approved",
                "independent_review_actor": approved["user"]["login"],
                "independent_review_id": approved.get("id"),
                "independent_review_source": source_sha, "owner_waiver": False}
    if not owner_waiver:
        raise ValueError("high-risk package requires structured independent GitHub APPROVED review or explicit owner waiver")
    if not independent_review_unavailable:
        raise ValueError("owner waiver requires explicit independent-review-unavailable assertion")
    if actor_login != owner_login:
        raise ValueError("owner waiver requires the repository-owner GitHub actor")
    if owner_waiver_source != source_sha:
        raise ValueError("owner waiver must be bound to the exact source SHA")
    reason = owner_waiver_reason.strip() if isinstance(owner_waiver_reason, str) else ""
    if not reason or len(reason) > 500:
        raise ValueError("owner waiver requires a non-empty bounded reason")
    return {"independent_review": "unavailable", "owner_waiver": True,
            "owner_actor": actor_login, "owner_waiver_source": source_sha,
            "owner_waiver_reason": reason}


def require_independent_review(scope: dict, comments: list[dict], source_sha: str) -> None:
    if not review_required(scope):
        return
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("independent review requires an exact source SHA")
    raise ValueError("plain PR comments cannot prove an independent GitHub review")
