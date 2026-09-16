# MAINT-LIFECYCLE-001 — acceptance contract candidate

Status: **staging / candidate acceptance contract**. This is not an active package and does not authorize lifecycle recovery.

Tracking defect: issue #188.
Frozen finishing source: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## Goal

Repair continuation when the finishing active package has `decides_next=true` and `next_package=null`, while preserving the repository's exact-source evidence, independent-review, dependency, rollback and branch-isolation guarantees.

## Before → after

### Before

A valid state may contain:

- one active package;
- active package `decides_next=true`;
- `next_package=null`.

But `transition()` requires `next_package == activate`, so no package can be selected. A genuinely new package also fails because it is absent from `PLAN.packages`.

### After

The CLI supports both:

1. existing preselected `planned_next` flow unchanged;
2. owner-selected next definition when and only when the current active package is allowed to decide next and `next_package` is null.

The selected package is validated before branch creation and state is written only on the newly created branch from the exact verified frozen head.

## Candidate input contract

A new package definition may contain only bounded product-independent metadata:

- `id`;
- `goal`;
- `depends_on`;
- optional `decides_next`;
- optional package metadata explicitly whitelisted by the final implementation.

It may not control:

- `status`;
- checkpoint/evidence;
- source/base SHA;
- working branch/canonical lineage;
- runtime base;
- workflow IDs;
- review outcome.

The candidate `id` must exactly match `--activate`.

## Acceptance cases

### A-01 Existing preselected next remains compatible

Given `PLAN.next_package=X` and `X.status=planned_next`, normal `begin-next --activate X` works with the same evidence/dependency checks as before.

### A-02 Valid decides-next selection

Given active `A.decides_next=true`, `next_package=null`, exact-source evidence passes, and validated candidate `B` directly depends on `A`, `begin-next` may create a new branch from the exact source and write state with `A=technical_pass`, `B=active`.

### A-03 Non-deciding active rejects selection

If the active package does not have `decides_next=true`, a candidate definition cannot be used to bypass `next_package`.

### A-04 Duplicate/reused package rejects

Candidate id already present as active/technical_pass/historical/superseded or otherwise ineligible is rejected before branch creation.

### A-05 Dependency boundary

Candidate must directly depend on the finishing package. Every additional dependency must exist and already have a ready status. Otherwise reject before branch creation.

### A-06 Control-field injection rejects

Unknown control fields, status/evidence/checkpoint/SHA/branch/lineage fields or malformed package ids are rejected before branch creation.

### A-07 Exact-source workflow failure creates no branch

Missing/wrong/stale required workflow evidence fails before any new branch is created.

### A-08 Independent-review failure creates no branch

When the finishing scope requires independent review, missing or wrong-SHA evidence fails before any new branch is created.

### A-09 Atomic write rollback

If PLAN/CURRENT/CHECKPOINTS writing fails after new-branch creation, original files are restored, checkout returns to the finishing branch and the new branch is deleted.

### A-10 Frozen branch remains byte-for-byte state-safe

Successful transition does not commit PLAN/CURRENT/CHECKPOINTS changes on the finishing source branch. Its ref remains at the exact evidence SHA.

### A-11 Candidate cannot choose the next-next package unless validated normally

The repair should not silently turn owner selection into arbitrary roadmap editing. `next_id` rules remain fail-closed and must directly depend on the newly activated package if used.

## Required tests

Extend `tests/test_project_state.py` with focused pure-model and orchestration cases for A-01…A-11. Use fake git/evidence/review hooks where appropriate so tests prove ordering, not only final state.

At minimum assert that evidence/review exceptions occur before a mocked `git switch -c` call.

## Documentation acceptance

If CLI syntax changes, update `docs/DEVELOPMENT.md` with:

- normal preselected-next invocation;
- decides-next candidate invocation;
- explicit statement that candidate input is not canonical state until transition succeeds on the new branch;
- no manual PLAN edit on a frozen source.

`DOCS_SYSTEM.md` changes only if ownership/state-transition wording actually becomes inaccurate.

## Security / safety review

Because the tool controls lineage and review-gate enforcement, any implementation that changes ordering of review/evidence checks or introduces a force/skip mode must be treated as a high-risk regression and rejected.

## Definition of done

- targeted project-state tests green;
- full docs/state/check-scope tests green;
- self-review explicitly traces A-01…A-11;
- no product/runtime source touched;
- required CI green for exact repair source;
- independent review evidence if repair scope remains high risk;
- source frozen after evidence.

## Self-review

PASS as a candidate acceptance contract. It describes behavior/tests without mutating canonical state or inventing a bypass for current gates.