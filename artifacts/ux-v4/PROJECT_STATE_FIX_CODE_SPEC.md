# Issue #188 — exact code-change specification

Status: **staging implementation specification / no canonical code modified**.

This document translates the accepted defect analysis into a narrow code design for `tools/project_state_model.py`, `tools/project_state.py` and `tests/test_project_state.py`.

## 1. Pure-model responsibility

Add a pure helper that validates/installs an owner-selected package definition into an in-memory copy of PLAN. Suggested responsibility, not mandatory symbol name:

```python
prepare_selected_package(plan, *, activate: str, definition: dict) -> dict
```

Required behavior:

- valid only when current `next_package is None`;
- current active package must have `decides_next=True`;
- `definition['id'] == activate`;
- reject if `activate` already exists in PLAN;
- whitelist candidate fields;
- require non-empty bounded `goal`;
- require `depends_on` list with current active package included directly;
- require every additional dependency to exist and be ready;
- normalize `decides_next` to bool/default false or the final explicitly chosen policy;
- create candidate internally as `planned_next`;
- set `next_package=activate` only in the returned in-memory copy;
- run normal `validate_plan()` before returning.

The helper must not mutate its input object.

## 2. Preserve existing transition()

Prefer keeping `transition()` strict about activating `PLAN.next_package`.

Reason: the repair should adapt owner-selected input into the same validated preselected form before calling the existing transition logic, instead of weakening the central invariant.

Flow:

```text
raw PLAN
  |
  | next already selected?
  |---- yes --> existing flow unchanged
  |
  |---- no + active.decides_next + definition
               |
               v
       prepare_selected_package(...)
               |
               v
        ordinary transition(...)
```

This minimizes regression risk and keeps `transition()` deterministic.

## 3. Candidate parser in project_state.py

Add a CLI argument for `begin-next`, for example:

```text
--define-package <json-file>
```

Exact flag name can differ, but semantics must be explicit.

Load candidate JSON without writing it to repository state. Validate:

- top-level JSON object;
- UTF-8;
- no duplicate/control semantics hidden in nested structures;
- file read errors become a fail-closed `PROJECT STATE ERROR`.

Do not allow the candidate file to set `status`, `checkpoint`, `evidence`, branch, SHA or lineage.

## 4. begin_next ordering

Current ordering already performs several correct checks. The repair must preserve and make testable this order:

```text
validate current PLAN
clean checkout
current branch == PLAN working_branch
source_head = HEAD
read active scope
if high risk: require independent review for source_head
fetch exact PR/workflow evidence for source_head
load + validate candidate in memory (if owner-selected mode)
compute updated state in memory
create new branch from source_head
write PLAN/CURRENT/CHECKPOINTS on new branch
rollback files + checkout + delete branch on write failure
```

Candidate validation may occur before evidence if it has no side effects, but **branch creation must occur only after both candidate validation and all required evidence/review checks pass**. Keep this ordering explicit in tests.

## 5. Mode rules

### Existing preselected mode

If `plan.next_package` is not null:

- `--define-package` should normally be rejected to avoid two competing sources of next-state intent;
- `--activate` must equal existing `next_package`;
- current behavior remains otherwise unchanged.

### Owner-selected mode

If `plan.next_package is None`:

- active package must `decides_next`;
- a validated definition is required when `activate` does not already exist as an eligible planned package;
- after in-memory preparation, reuse normal transition validation.

If the final implementation supports selecting an already-existing `planned` package, define that rule explicitly and still require direct dependency on the finishing package. Do not infer eligibility from package name.

## 6. Package id validation

Use a deterministic conservative id pattern consistent with existing package ids. For example:

```text
^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$
```

Do not silently uppercase malformed input. Reject ambiguity.

## 7. Candidate field whitelist

Minimum:

```text
id
goal
depends_on
decides_next
```

If optional metadata is needed, add each field deliberately. Unknown fields should fail rather than be ignored because ignored fields can conceal operator assumptions.

Explicitly forbidden:

```text
status
checkpoint
evidence
canonical_lineage
runtime_base
working_branch
current_package_base
source_head
sha
pr
workflows
risk
scope
```

Risk/scope belong to the actual package scope manifest, not PLAN package definition input.

## 8. Checkpoint behavior

On successful transition:

- finishing active package becomes `technical_pass` with checkpoint reference;
- exact evidence is added to `CHECKPOINTS.json` under finishing package id;
- selected repair/new package becomes active;
- lineage `current_package_base` becomes finishing working branch + exact frozen source SHA;
- lineage `working_branch` becomes the newly created branch.

Do not copy full workflow evidence into PLAN.

## 9. Regression tests to add

Pure model:

- prepare selection returns new object and leaves source unchanged;
- valid definition produces `planned_next` + `next_package` then ordinary transition passes;
- reject active without `decides_next`;
- reject id mismatch/reuse/malformed id;
- reject missing finishing dependency;
- reject unready dependency;
- reject unknown/forbidden candidate fields;
- existing preselected flow unchanged.

Orchestration:

- candidate read/validation failure → no `git switch -c`;
- independent-review failure → no `git switch -c`;
- PR/workflow evidence failure → no `git switch -c`;
- valid mode → branch created only after checks;
- write failure → exact old PLAN/CURRENT/CHECKPOINTS bytes restored, original branch restored, new branch deleted.

CLI:

- missing definition in owner-selected-new-package mode fails with actionable text;
- `--define-package` supplied when preselected next already exists fails clearly;
- malformed JSON returns exit code 2 through current error handling.

## 10. What not to refactor

Do not combine this with:

- generic GitHub client abstraction;
- PLAN schema redesign;
- package status taxonomy rewrite;
- review-evidence parser changes unless a failing test proves necessity;
- branch naming policy changes;
- product roadmap edits;
- FRONTEND-002 UX work.

## 11. Suggested implementation sequence

1. Add failing pure-model tests.
2. Add failing orchestration ordering tests.
3. Implement candidate validation/preparation helper.
4. Wire candidate CLI/input into `begin_next`.
5. Run targeted project-state tests.
6. Run docs/state/scope regression suites.
7. Update DEVELOPMENT only for real CLI behavior.
8. SELF_REVIEW against `MAINT_LIFECYCLE_001_ACCEPTANCE.md`.
9. Full CI and independent review according to actual risk manifest.

## Self-review

PASS as a code specification: it keeps the strict transition invariant, reuses the existing validated path, enumerates fail-closed input rules, and avoids product/runtime changes.