"""Exact owner authorization for one product merge plus its next mechanical closeout merge."""
from __future__ import annotations

import re
from pathlib import Path

from project_state_model import ROOT

SHA_RE = re.compile(r"[0-9a-f]{40}")


def authorization_body(pr_number: int, source_head: str) -> str:
    return (
        f"Owner merge authorization for PR #{pr_number}: APPROVE\n"
        f"Source HEAD: {source_head}\n"
        "Mechanical closeout merge: AUTHORIZED"
    )


def find_authorization(
    comments: list[dict],
    pr_number: int,
    source_head: str,
    owner_login: str,
    *,
    before: str | None = None,
) -> dict | None:
    if not SHA_RE.fullmatch(source_head):
        raise ValueError("owner merge authorization requires exact source SHA")
    expected = authorization_body(pr_number, source_head)
    cutoff = None
    if before is not None:
        from project_state_provenance import _time
        cutoff = _time(before, "owner authorization cutoff")
    for row in comments:
        if (
            (row.get("user") or {}).get("login") != owner_login
            or row.get("author_association") != "OWNER"
            or str(row.get("body") or "").strip() != expected
        ):
            continue
        created, updated = row.get("created_at"), row.get("updated_at")
        if not created or not updated:
            continue
        if cutoff is not None:
            from project_state_provenance import _time
            if (
                _time(created, "owner authorization creation") >= cutoff
                or _time(updated, "owner authorization update") >= cutoff
            ):
                continue
        if type(row.get("id")) is int:
            return row
    return None


def fetch_authorization(
    pr_number: int,
    source_head: str,
    *,
    root: Path = ROOT,
) -> dict:
    from project_state_evidence import _flatten_pages, gh_json, repo_slug

    try:
        slug = repo_slug(root)
        owner = slug.split("/", 1)[0]
        comments = _flatten_pages(gh_json(
            ["api", "--paginate", "--slurp",
             f"repos/{slug}/issues/{pr_number}/comments?per_page=100"],
            root=root,
        ))
    except (AssertionError, OSError, ValueError):
        return {"mechanical_closeout_merge_authorized": False}
    row = find_authorization(comments, pr_number, source_head, owner)
    if row is None:
        return {"mechanical_closeout_merge_authorized": False}
    return {
        "mechanical_closeout_merge_authorized": True,
        "mechanical_closeout_authorization_comment_id": row["id"],
    }


def authenticate_checkpoint_authorization(
    checkpoint: dict,
    pr_number: int,
    source_head: str,
    slug: str,
    *,
    before: str,
    root: Path = ROOT,
) -> dict:
    if checkpoint.get("mechanical_closeout_merge_authorized") is not True:
        return {}
    from project_state_evidence import _flatten_pages, gh_json

    comments = _flatten_pages(gh_json(
        ["api", "--paginate", "--slurp",
         f"repos/{slug}/issues/{pr_number}/comments?per_page=100"],
        root=root,
    ))
    row = find_authorization(
        comments, pr_number, source_head, slug.split("/", 1)[0], before=before,
    )
    expected_id = checkpoint.get("mechanical_closeout_authorization_comment_id")
    if row is None or row.get("id") != expected_id:
        raise ValueError("checkpoint owner merge authorization cannot be authenticated")
    return {
        "mechanical_closeout_merge_authorized": True,
        "mechanical_closeout_authorization_comment_id": expected_id,
    }
