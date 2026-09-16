# FRONTEND-001 — review coordination

Status: **staging coordination note**.

Exact frozen source: `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## Current gate state

- required exact-head CI: PASS;
- self-review: PASS;
- owner visual acceptance: PENDING;
- independent review: PENDING;
- PR #36: open, draft, unmerged;
- continuation tooling issue #188: OPEN.

## Review packets

Owner review:
- `FRONTEND_001_VISUAL_AUDIT.md`;
- `OWNER_VISUAL_ACCEPTANCE_CHECKLIST.md`.

Independent reviewer:
- `INDEPENDENT_REVIEW_CHECKLIST.md`;
- frozen-source PR #36 diff and `docs/reviews/FRONTEND-001.md`;
- exact-head workflow evidence.

Machine-readable status:
- `FRONTEND_001_GATE_STATUS.json`.

## Coordination rule

PR comments requesting review must never contain a forged machine PASS marker. Owner acceptance and independent review are separate gates and neither is inferred from CI, screenshots, this staging branch, or a generic “looks good” comment.

## Continuation rule

Even after both human gates are closed, do not use manual PLAN mutation to start the next package. Issue #188 must be resolved or an explicitly approved fail-closed recovery procedure must be used without changing the frozen source evidence retroactively.
