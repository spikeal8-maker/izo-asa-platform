"""Exact owner authorization may cover one product merge and its next mechanical closeout merge."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from project_state_owner_authorization import authorization_body, find_authorization


def comment(pr=77, head="a" * 40, *, owner="owner", created="2026-10-05T00:00:00Z"):
    return {
        "id": 91,
        "user": {"login": owner},
        "author_association": "OWNER",
        "created_at": created,
        "updated_at": created,
        "body": authorization_body(pr, head),
    }


def test_exact_owner_authorization_is_bound_to_pr_and_sha():
    head = "a" * 40
    row = comment(head=head)
    assert find_authorization([row], 77, head, "owner") == row
    assert find_authorization([row], 78, head, "owner") is None
    assert find_authorization([row], 77, "b" * 40, "owner") is None


def test_foreign_edited_or_late_authorization_fails_closed():
    head = "a" * 40
    foreign = comment(head=head, owner="other")
    assert find_authorization([foreign], 77, head, "owner") is None

    edited = comment(head=head)
    edited["body"] += "\nextra"
    assert find_authorization([edited], 77, head, "owner") is None

    late = comment(head=head, created="2026-10-05T00:02:00Z")
    assert find_authorization(
        [late], 77, head, "owner", before="2026-10-05T00:01:00Z",
    ) is None
