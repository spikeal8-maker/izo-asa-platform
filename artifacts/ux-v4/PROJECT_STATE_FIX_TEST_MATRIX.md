# Issue #188 — project_state repair test matrix

Status: **staging / test design**. This is a precise test plan for the maintenance repair, not executed evidence.

Target owners: `tools/project_state_model.py`, `tools/project_state.py`, `tests/test_project_state.py`.

## Pure-model cases

| Test candidate | Setup | Expected result |
|---|---|---|
| `test_prepare_selected_package_accepts_valid_decides_next_definition` | active decides next, `next_package=None`, new id, direct finishing dependency | returned plan has candidate `planned_next` and `next_package` set; input plan unchanged |
| `test_prepare_selected_package_rejects_when_active_does_not_decide_next` | same candidate, active `decides_next=false` | `ValueError`; no mutation |
| `test_prepare_selected_package_rejects_id_mismatch` | `activate=A`, definition id B | reject |
| `test_prepare_selected_package_rejects_existing_package_id` | candidate id already in packages | reject regardless of completed/active/planned status unless a separately specified existing-planned selection rule is implemented |
| `test_prepare_selected_package_requires_finishing_dependency` | candidate dependencies omit active package | reject |
| `test_prepare_selected_package_rejects_unready_extra_dependency` | extra dependency status planned/unready | reject |
| `test_prepare_selected_package_rejects_unknown_control_fields` | definition contains status/checkpoint/evidence/sha/branch/risk/scope/unknown field | reject |
| `test_prepare_selected_package_rejects_malformed_id_and_goal` | invalid id or blank/invalid goal | reject |
| `test_preselected_transition_remains_unchanged` | current `planned_next` plan fixture | existing `transition()` behavior remains PASS |

## Orchestration ordering cases

Use a fake `git()` recorder and monkeypatched evidence/review functions. Assert exact call ordering where safety matters.

### Review failure before branch creation

Setup high-risk finishing scope and no valid independent-review marker.

Expected:

- exception from review requirement;
- no `git switch -c` call;
- PLAN/CURRENT/CHECKPOINTS untouched.

### PR/workflow evidence failure before branch creation

Setup candidate valid in memory but `fetch_pr_evidence` raises.

Expected:

- no branch creation;
- no state write.

### Candidate validation failure before branch creation

Setup exact evidence/review PASS mocks, malformed candidate.

Expected:

- candidate rejected before `git switch -c`;
- no state write.

### Valid owner-selected transition

Expected call boundary:

```text
status --porcelain
branch --show-current
rev-parse HEAD
(review/evidence checks)
(candidate validation / transition calculation)
switch -c <new-branch> <exact-source>
write_state(...)
```

Assert new lineage base equals exact finishing SHA and working branch equals new branch.

### Write failure rollback

Reuse and extend existing rollback test:

- create new branch;
- simulate partial writes then raise;
- original PLAN/CURRENT/CHECKPOINTS bytes restored;
- switch back to original branch;
- delete new branch;
- no orphan state.

## CLI cases

| Invocation | Expected |
|---|---|
| preselected next without definition | existing behavior |
| null next + new activate + no definition | clear fail-closed error |
| null next + valid definition | proceeds to normal evidence/transition path |
| preselected next + definition also supplied | reject competing next-state sources |
| malformed JSON definition | exit code 2 / `PROJECT STATE ERROR` |
| definition unreadable/non-object | fail closed |

## Regression assertions

Keep existing assertions for:

- one active package;
- direct next dependency;
- ready dependency statuses;
- exact PR merge-tree evidence;
- required workflows;
- compact PLAN agent-context budget;
- rollback on state-write failure.

Do not delete or loosen an existing test to fit the repair.

## Evidence boundary

These tests prove control-flow and state integrity. They do not substitute for an exact-head PR workflow run or independent review of the actual repair source.

## Self-review

The matrix covers success, malformed input, dependency boundaries, review/evidence ordering, backward compatibility and rollback. No test assumes product-specific `FRONTEND-002` behavior.