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
