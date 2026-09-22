"""Structured review evidence and explicit owner-waiver semantics."""
from __future__ import annotations
import re

SHA_RE = re.compile(r"[0-9a-f]{40}")


def review_required(scope: dict) -> bool:
    return scope.get("risk") == "high" or scope.get("independent_review_required") is True


def matching_structured_review(reviews: list[dict], source_sha: str, owner_login: str) -> dict | None:
    if not SHA_RE.fullmatch(source_sha):
        return None
    for review in reviews:
        user = review.get("user") or {}
        login = user.get("login")
        if (str(review.get("state", "")).upper() == "APPROVED"
                and review.get("commit_id") == source_sha and isinstance(login, str)
                and login and login != owner_login):
            return review
    return None


def review_decision(scope: dict, reviews: list[dict], source_sha: str, *, owner_login: str,
                    actor_login: str | None = None, owner_waiver: bool = False,
                    independent_review_unavailable: bool = False,
                    owner_waiver_source: str | None = None,
                    owner_waiver_reason: str | None = None) -> dict:
    if not review_required(scope):
        return {"independent_review": "not_required", "owner_waiver": False}
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("review evidence requires an exact source SHA")
    approved = matching_structured_review(reviews, source_sha, owner_login)
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
    """Legacy compatibility: plain PR comments are never authoritative evidence."""
    if not review_required(scope):
        return
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("independent review requires an exact source SHA")
    raise ValueError("plain PR comments cannot prove an independent GitHub review")
