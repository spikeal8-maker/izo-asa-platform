"""Time-bound GitHub evidence for accepted checkpoint and closeout transitions."""
from __future__ import annotations

from datetime import datetime
import hashlib
import re
from pathlib import Path

from project_state_model import ROOT

REQUIRED = ("Foundation CI", "Dependency Security", "Review Source")


def _time(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{label} timestamp missing or invalid") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{label} timestamp lacks timezone")
    return parsed


def require_pr_runs_before(runs: dict[str, dict], cutoff: str, label: str) -> None:
    """The selected latest successful PR attempts must have finished in their stage."""
    deadline = _time(cutoff, label)
    for name, run in runs.items():
        stamp, attempt = run.get("updatedAt"), run.get("runAttempt")
        if (type(attempt) is not int or attempt < 1 or not stamp
                or _time(stamp, f"{name} workflow update") >= deadline):
            raise ValueError(f"required PR workflow {name!r} lacks successful pre-{label} attempt")


def require_current_approval_before(reviews: list[dict], decision: dict,
                                    head: str, cutoff: str) -> None:
    """Keep the full current verdict, then fence its selected approval by merge time."""
    if decision.get("independent_review") != "approved":
        return
    deadline = _time(cutoff, "closeout merge")
    selected = next((row for row in reviews
        if row.get("id") == decision.get("independent_review_id")
        and row.get("commit_id") == head and str(row.get("state", "")).upper() == "APPROVED"
        and (row.get("user") or {}).get("login") == decision.get("independent_review_actor")), None)
    if (selected is None or not selected.get("submitted_at")
            or _time(selected["submitted_at"], "closeout approval") >= deadline):
        raise ValueError("current exact-head structured approval must precede closeout merge")


def _historical_waiver_body(body: str, source: str, runs: dict) -> bool:
    # Exact legacy owner statement: PR #250 issuecomment-5893520488.
    lines = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    return (source == "9bed77548d07f113bc806b1e5016076edb2646e1"
            and {name: runs[name]["databaseId"] for name in REQUIRED} ==
            {"Foundation CI": 36590236580, "Dependency Security": 36590236563,
             "Review Source": 36590236588}
            and hashlib.sha256(lines.encode("utf-8")).hexdigest() ==
            "cc8ea5fa2bc25dc09038f4837dedfed736425d11e0af3f9650e1671273cbd7e1")


def legacy_pr252_review(pr_number: int, head: str, merge: str, pr: dict,
                        workflows: dict, slug: str, *, root: Path = ROOT) -> dict:
    """One historical owner-authenticated closeout record, never a future waiver."""
    from project_state_evidence import gh_json, git

    expected_head = "afb7ce498f2aecdbbfaf10a652e5591f2c7d9ccd"
    expected_merge = "95f153acc3a7a3ce4163d2e59b6f3e44ba963906"
    expected_runs = {"Foundation CI": 36592337411,
                     "Dependency Security": 36592337156,
                     "Review Source": 36592337428}
    if (pr_number != 252 or head != expected_head or merge != expected_merge
            or pr.get("headRefOid") != expected_head
            or (pr.get("mergeCommit") or {}).get("oid") != expected_merge
            or pr.get("mergedAt") != "2026-09-29T15:59:52Z"
            or slug != "spikeal8-maker/izo-asa-platform"
            or workflows != expected_runs):
        raise ValueError("PR #252 legacy closeout identity or required CI IDs mismatch")
    main = git("ls-remote", "origin", "refs/heads/main", root=root).split()
    if (len(main) != 2 or not re.fullmatch(r"[0-9a-f]{40}", main[0])
            or main[1] != "refs/heads/main"):
        raise ValueError("PR #252 legacy closeout canonical main lineage mismatch")
    if main[0] != expected_merge:
        lineage = gh_json(["api", f"repos/{slug}/compare/{expected_merge}...{main[0]}"],
                          root=root)
        if (not isinstance(lineage, dict) or lineage.get("status") != "ahead"
                or (lineage.get("base_commit") or {}).get("sha") != expected_merge
                or (lineage.get("head_commit") or {}).get("sha") != main[0]):
            raise ValueError("PR #252 legacy closeout canonical main lineage mismatch")
    row = gh_json(["api", f"repos/{slug}/issues/comments/5893861963"], root=root)
    if (not isinstance(row, dict) or row.get("id") != 5893861963
            or row.get("issue_url") != f"https://api.github.com/repos/{slug}/issues/252"
            or (row.get("user") or {}).get("login") != "spikeal8-maker"
            or row.get("author_association") != "OWNER"
            or row.get("created_at") != "2026-09-29T15:59:25Z"
            or not row.get("updated_at")
            or _time(row["created_at"], "PR #252 legacy review creation") >=
                _time(pr["mergedAt"], "PR #252 closeout merge")
            or _time(row["updated_at"], "PR #252 legacy review update") >=
                _time(pr["mergedAt"], "PR #252 closeout merge")):
        raise ValueError("PR #252 legacy owner comment identity or timing mismatch")
    lines = "\n".join(line.strip() for line in str(row.get("body") or "").splitlines()
                      if line.strip())
    if (expected_head not in lines or "APPROVE" not in lines
            or any(f"{name} `{run_id}`: SUCCESS" not in lines
                   for name, run_id in expected_runs.items())
            or hashlib.sha256(lines.encode("utf-8")).hexdigest() !=
                "e8d396a134c9f32dcecb7fde1b639f835d96566fa139d7bc6c2795a8dba97b1e"):
        raise ValueError("PR #252 legacy owner comment body or CI evidence mismatch")
    return {"independent_review": "legacy_owner_authenticated",
            "independent_review_source": expected_head,
            "legacy_closeout_comment_id": 5893861963,
            "owner_waiver": False}


def _structured_waiver_body(body: str, pr_number: int, head: str,
                            workflows: dict, *, source_checkpoint: bool = False) -> str | None:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) != 7 or not lines[3].startswith("Reason: "):
        return None
    reason = lines[3][len("Reason: "):]
    if re.search(r"\b(?:I reject|I deny|I refuse|do not approve|not approved|no owner waiver)\b",
                 reason, flags=re.IGNORECASE):
        return None
    declaration = f"Owner waiver for {'source checkpoint ' if source_checkpoint else ''}PR #{pr_number}: APPROVE"
    expected = [declaration, f"Source HEAD: {head}", "Independent review: unavailable",
                f"Reason: {reason}",
                *(f"{name}: {workflows[name]} SUCCESS" for name in REQUIRED)]
    return reason if lines == expected and 0 < len(reason) <= 500 else None


def _source_waiver_body(body: str, pr_number: int, head: str, runs: dict,
                        reason: str | None) -> bool:
    if pr_number == 250 and _historical_waiver_body(body, head, runs):
        return reason == (
            "Final exact-head independent read-only challenge APPROVE for source "
            "9bed77548d07f113bc806b1e5016076edb2646e1; separate GitHub reviewer "
            "actor unavailable. Owner authorizes only PRE-P1 terminal closeout; Chat P1 remains unstarted.")
    ids = {name: runs[name]["databaseId"] for name in REQUIRED}
    stated = _structured_waiver_body(body, pr_number, head, ids, source_checkpoint=True)
    return stated is not None and stated == reason


def _closeout_owner_waiver(pr_number: int, head: str, workflows: dict,
                           merged_at: str, slug: str, *, root: Path = ROOT) -> tuple[str, int] | None:
    from project_state_evidence import gh_json, _flatten_pages

    cutoff = _time(merged_at, "closeout merge")
    comments = _flatten_pages(gh_json(["api", "--paginate", "--slurp",
        f"repos/{slug}/issues/{pr_number}/comments?per_page=100"], root=root))
    owner = slug.split("/", 1)[0]
    for row in comments:
        if ((row.get("user") or {}).get("login") != owner
                or row.get("author_association") != "OWNER"):
            continue
        reason = _structured_waiver_body(str(row.get("body") or ""),
                                          pr_number, head, workflows)
        if (reason is None or type(row.get("id")) is not int
                or not row.get("created_at") or not row.get("updated_at")):
            continue
        if max(_time(row[key], "closeout owner comment")
               for key in ("created_at", "updated_at")) < cutoff:
            return reason, row["id"]
    return None
