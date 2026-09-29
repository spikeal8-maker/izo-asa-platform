# LINEAGE-001 · OpenRouter lineage reconciliation

## Scope

Canonical base for this package: `docs/final-guardrails` frozen source `b53328d5e9e9111196d49062424cd7e386ac1eaa`.
Working branch: `lineage/reconcile-openrouter`. No runtime/provider/network behavior is changed in LINEAGE-001.
The task is to decide what from PR #15/#16/#17/#19/#20/#21 may influence future canonical work.

## Evidence inspected

| PR | Head | Purpose | GitHub Foundation |
|---|---|---|---|
| #15 | `4db9c36…` | first OpenRouter API-001 | FAIL |
| #16 | `ba35c76…` | hardened OpenRouter API-001 | PASS · 700 Python; browser had 2 retries |
| #17 | `b39ce60…` | alternate clean OpenRouter API-001 | PASS |
| #19 | `8567578…` | typed Settings lifecycle | PASS · 714 Python; 1 browser retry |
| #20 | `f5ec5b4…` | Catalog backend | PASS · 737 Python · 400/400 browser |
| #21 | `f3d19fc…` | Catalog admin UI | FAIL · 3 permission/navigation viewport cases |

PR bodies are snapshots only; actual PR heads/checks and code deltas were inspected separately.

## API-001 disposition

OpenRouter client/config/worker, pools, endpoint assumptions and provider execution are **not salvaged**.
Canonical fal already has a stronger dedicated queue contract, unknown-submit handling, durable provider calls,
recovery and budget-gated admission. Reintroducing a second provider runtime here would recreate split lineage.
## SETTINGS-001 disposition

PR #19 is structurally provider-neutral. Its `PlanPolicy` types still match the current Entitlements code;
there is no schema/migration drift in those runtime modules. Useful reference:

- typed descriptors instead of free-form key/value settings;
- preview with strict validation and explicit missing-required fields;
- `expected_revision` optimistic concurrency;
- publish into existing immutable entitlement revisions/default;
- rollback by publishing a new revision, never rewriting history;
- accepted jobs keep their stored plan/execution snapshot.

Not accepted as current code: the package introduced `plans.write` but no canonical operator delegation path;
its tests inserted permission rows directly. `SETTINGS-002` must re-author this lifecycle after `ACCESS-001`.

## CATALOG-001 backend disposition

PR #20 contributes design patterns only: versioned capability/connection heads, immutable revisions,
credential metadata without raw secrets, rotation/revoke, offline evidence binding and audit/idempotency receipts.
Provider-specific code is rejected: OpenRouter literals, endpoint, env secret ref, adapter ID, capability IDs,
`runtime.py` resolver and changes that make Job admission depend on the OpenRouter catalog.

Current fal `jobs.catalog` + `FalSettings` + provider-call tables remain runtime authority until a new explicit
contract says otherwise. Old `0010_catalog.py` is historical reference, not a migration to cherry-pick.
## Catalog UI disposition

PR #21 is not a technically accepted UI implementation. Its Foundation failure was reproducible across
phone-small/phone/tablet: catalog-only staff could open Models but the expected administration navigation link
was absent because existing shell/admin navigation was tied to unrelated user-admin permission semantics.
Useful reference only: no raw-key field, credential fingerprint display, operation-id reuse after uncertain
mutation outcome, and explicit `network_called=false` / `live_ready=false` presentation.

## Access gap discovered

Both Settings and Catalog introduced granular permissions without implementing A-28/AD-09 provisioning.
That is a shared prerequisite, not a reason to weaken server checks or insert permissions manually. Therefore
`ACCESS-001` is promoted to the single next canonical package before Settings/Catalog reimplementation.

## Final disposition

- OpenRouter provider runtime: historical only; no cherry-pick.
- SETTINGS-001: `superseded_reference` → re-author as `SETTINGS-002` after ACCESS-001.
- CATALOG-001 backend: `superseded_reference` → re-author neutral control plane as `CATALOG-002`.
- Catalog UI: failed implementation reference → `CATALOG-UI-002` after backend.
- `LOCAL-001` dependency moves from old CATALOG-001 to CATALOG-002.
- Old PRs remain open Draft references; no close/merge/deploy action is implied.

**Verdict: RECONCILIATION COMPLETE · FAL LINE REMAINS CANONICAL · NEXT ACCESS-001 · NO RUNTIME CHANGE**

## Self-review / local verification

- `project_state begin-next` started this package from frozen DOC-004D source `b53328d5e9e9111196d49062424cd7e386ac1eaa` using verified PR #26 evidence.
- PR #15/#16/#17/#19/#20/#21 heads, file deltas, bodies and GitHub checks were inspected; PR #21 failure log was read to the concrete catalog-only navigation assertion.
- Current fal `jobs.catalog`, `FalSettings`, provider-call lifecycle and admin permission provisioning were compared against the old lineage rather than inferred from PR titles.
- `tests/test_docs_system.py`, `tests/test_project_state.py`, `tests/test_change_scope.py` and every `test_*boundaries.py`: **104/104 PASS**.
- `python tools/check_docs.py` — PASS: `LINEAGE-001 → ACCESS-001`, 22 blocks, 15 routes.
- `python tools/project_state.py verify` — PASS.
- Live docs stale scan: no `SETTINGS-001`, `CATALOG-001`, `hold_for_reconciliation` or `до LINEAGE-001` remains in current routing docs; historical ADR/review/STATUS references are intentional evidence.
- Scope guard: **12/12**, outside scope 0, sensitive violations 0.
- `git diff --check` — PASS.
- No runtime Python/TypeScript, migrations, dependency locks, compose, workflow, OpenAPI contract or provider settings were changed.

Full GitHub CI remains required before this source SHA can become the next frozen checkpoint. Merge/deploy/live provider calls and closure of historical PRs are not part of LINEAGE-001.
