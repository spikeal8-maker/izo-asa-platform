# IZO ASA — one-time lifecycle recovery protocol candidate

Status: **staging proposal only / explicit owner approval required before use**.

This document exists because issue #188 makes the normal `project_state.py begin-next` path impossible from the current valid state (`FRONTEND-001.decides_next=true`, `next_package=null`). It is not permission to bypass lifecycle controls.

Frozen finishing source: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## Preferred resolution

The preferred solution is to repair `project_state` so the normal tool can atomically select/define the next package after verifying the frozen source. See `PROJECT_STATE_DECIDES_NEXT_PATCH_PREVIEW.md` and issue #188.

## Why a recovery protocol may still be needed

The repair itself cannot currently be activated as a normal next package because the broken transition is exactly what would activate it. Therefore there is a bootstrap paradox.

A one-time recovery procedure is acceptable only if explicitly approved by the owner after FRONTEND-001 owner acceptance and independent review are both complete, and only if it preserves the same safety properties the normal tool is supposed to enforce.

## Preconditions

All must be true before any recovery action:

1. `ux/frontend-reset` still points exactly to `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.
2. PR #36 is still resolvable for that exact head.
3. Foundation CI, Dependency Security and Review Source for that exact head are successful.
4. Owner visual acceptance is explicitly recorded for that exact head.
5. Independent-review evidence required by `tools/review_evidence.py` is present for that exact head.
6. Working checkout is clean.
7. Owner explicitly approves the one-time recovery procedure itself.

If any precondition is false, stop.

## Candidate bootstrap target

The bootstrap target should be a maintenance-only package such as `MAINT-LIFECYCLE-001`, not `FRONTEND-002` directly.

Reason: repair lifecycle tooling first, verify it, then let the repaired tooling start product packages normally. Do not combine process-control repair with Chat/UX changes.

Candidate scope is recorded in:

- `ISSUE_188_REPAIR_SCOPE.md`;
- `project-state-188-candidate.json`.

## Required recovery properties

A one-time recovery implementation must perform the equivalent of the normal safe transition:

1. re-verify exact frozen SHA and PR/workflow evidence;
2. re-verify independent-review evidence;
3. validate the maintenance package definition entirely in memory;
4. create a new branch **exactly from the frozen source SHA**;
5. only on that new branch write:
   - `PLAN.json` with FRONTEND-001 moved to technical_pass/checkpoint and MAINT-LIFECYCLE-001 active;
   - `CURRENT.md` rendered from the new PLAN;
   - `CHECKPOINTS.json` with FRONTEND-001 evidence;
6. add the maintenance scope manifest as part of the new package work;
7. if any state write fails, restore files and delete the new branch;
8. never write state to `ux/frontend-reset`.

## Forbidden shortcuts

- editing `PLAN.json` directly on `ux/frontend-reset`;
- creating a product continuation branch and pretending `begin-next` succeeded;
- marking independent review complete without exact-source evidence;
- using `docs/ux-spec-v4-staging` as the package base;
- merging staging artifacts into canonical docs as a workaround;
- changing the frozen source first and rerunning only part of CI;
- activating `FRONTEND-002` before lifecycle tooling itself is repaired and checkpointed.

## After bootstrap

`MAINT-LIFECYCLE-001` should implement issue #188, add its regression tests, run normal SELF_REVIEW and full required CI, and freeze.

After the repair package is verified, the next product package can be created with the repaired `begin-next` path. The prepared candidate remains the bounded Chat/docs reconciliation described by `NEXT_PACKAGE_SCOPE_CANDIDATE.md`.

## Audit requirement

Any executed recovery must leave an auditable record containing:

- approved recovery decision;
- exact finishing source SHA;
- PR and workflow IDs used as evidence;
- independent-review evidence reference;
- new branch name and first state commit;
- exact before/after PLAN state;
- confirmation that `ux/frontend-reset` did not move.

## Self-review

This proposal does not execute the recovery. It exposes the bootstrap paradox, chooses a maintenance-only target, preserves exact-source evidence, and requires explicit owner approval before any exceptional path is used.