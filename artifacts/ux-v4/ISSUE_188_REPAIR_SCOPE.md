# Issue #188 — bounded repair scope

Status: **staging repair scope / not an active package**.

Problem: current lifecycle deadlocks when an active `decides_next=true` package has `next_package=null`; `transition()` still requires the requested activation to equal `PLAN.next_package`.

## Repair goal

Allow an owner-selected next package to be defined/validated entirely in memory and activated atomically on the newly created branch, while preserving exact frozen-source evidence and existing preselected-next behavior.

## Candidate files

Primary:
- `tools/project_state_model.py`;
- `tools/project_state.py`;
- `tests/test_project_state.py`.

Only if required by the final design:
- `docs/DEVELOPMENT.md` for the new CLI contract;
- `docs/DOCS_SYSTEM.md` if state-transition ownership wording needs clarification.

No product/frontend/backend business source belongs in this repair.

## Mandatory invariants

1. Evidence for the finishing package is checked against its exact frozen source before a new branch is created.
2. Independent-review requirement for the finishing package is checked before branch creation.
3. `PLAN`, `CURRENT` and `CHECKPOINTS` are not mutated on the frozen finishing branch.
4. A new package id cannot collide with an active/completed package.
5. The new package must directly depend on the finishing package.
6. All additional dependencies must already be ready.
7. Candidate metadata is validated before branch creation.
8. Existing `planned_next` transition behavior remains supported.
9. Write failure restores original state and deletes the newly created branch.
10. No broad “ignore validation” or force flag is introduced.

## Required tests

- decides-next + null next + valid new package → accepted in memory, branch/state written only after evidence;
- active package without `decides_next` → rejected;
- duplicate/completed package id → rejected;
- missing direct finishing dependency → rejected;
- unready extra dependency → rejected;
- malformed id/goal/definition → rejected;
- independent-review failure → no branch creation;
- workflow/evidence failure → no branch creation;
- write failure after branch creation → rollback branch + PLAN/CURRENT/CHECKPOINTS;
- current preselected `planned_next` path stays green.

## Risk

This is lifecycle/control-plane tooling. Treat as at least `medium`, and `high` if the chosen implementation can bypass or weaken review/evidence gates.

## Non-goals

- no automatic package selection;
- no implicit owner decision inferred from branch names;
- no mutation of frozen source to pre-seed `next_package`;
- no merge/deploy behavior;
- no product roadmap changes;
- no relaxation of exact-head evidence.

## Self-check

This scope repairs only the transition mechanism. It does not decide which product package should follow FRONTEND-001 and does not authorize manual continuation before the current gates close.