"""Machine-checkable independent-review evidence bound to an exact source SHA."""
from __future__ import annotations

import re

MARKER = re.compile(
    r"(?im)^INDEPENDENT_REVIEW\s+PASS\s+source=([0-9a-f]{40})\s+reviewer=(\S+)\s*$"
)


def review_required(scope: dict) -> bool:
    return scope.get("risk") == "high" or scope.get("independent_review_required") is True


def matching_review(comments: list[dict], source_sha: str) -> dict | None:
    for comment in comments:
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        match = MARKER.search(body)
        if match and match.group(1) == source_sha and match.group(2).strip():
            return comment
    return None


def require_independent_review(scope: dict, comments: list[dict], source_sha: str) -> None:
    if not review_required(scope):
        return
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("independent review requires an exact source SHA")
    if matching_review(comments, source_sha) is None:
        raise ValueError(
            "high-risk package requires PR comment: "
            f"INDEPENDENT_REVIEW PASS source={source_sha} reviewer=<reviewer>"
        )
