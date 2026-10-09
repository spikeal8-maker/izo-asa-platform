"""Review evidence for open and already merged source PRs."""
from __future__ import annotations
from pathlib import Path

def merged_transition_evidence(plan: dict, pr: int, source_head: str, review: dict, root: Path,
                               *, active_scope, fetch_pr_evidence, fetch_review_evidence) -> dict:
    scope = active_scope(plan, root=root)
    evidence = fetch_pr_evidence(pr, source_head, root=root)
    if evidence.get("merged_source_commit"):
        from project_state_provenance import _closeout_owner_waiver
        from project_state_evidence import repo_slug
        if any(review.values()):
            raise ValueError("merged source PR review must reuse authenticated pre-merge evidence")
        waiver = _closeout_owner_waiver(pr, source_head, evidence["workflows"],
                                        evidence["merged_at"], repo_slug(root), root=root,
                                        source_checkpoint=True)
        review = (dict(owner_waiver=True, independent_review_unavailable=True,
                       owner_waiver_source=source_head, owner_waiver_reason=waiver[0])
                  if waiver is not None else {})
        decision = fetch_review_evidence(scope, pr, source_head, root=root,
                                         approved_before=evidence["merged_at"], **review)
        if waiver is not None and decision.get("owner_waiver") is True:
            evidence["source_waiver_comment_id"] = waiver[1]
        evidence.pop("merged_at")
    else:
        decision = fetch_review_evidence(scope, pr, source_head, root=root, **review)
    evidence.update(decision)
    return evidence

