# IZO ASA UX SPEC v4 — staging artifact

This directory stores the complete UX SPEC v4 produced for `spikeal8-maker/izo-asa-platform`.

**Status:** non-canonical staging artifact. It must not be treated as a second `PRODUCT/UX/ADMIN` source of truth. Canonical reconciliation belongs in a later lifecycle package after the current frozen `FRONTEND-001` gates and continuation tooling allow a safe transition.

## Exact source snapshot

- repository: `spikeal8-maker/izo-asa-platform`
- source branch checked: `ux/frontend-reset`
- source head checked: `5c0e79b6fc3a7120207d0889b176fbfed3dab973`
- complete archive SHA-256: `ed4dfc898f589d4e81d3d2eb1d53086ccb0fec1ccb06a9a4126b23bbad7a3897`
- archive contains 29 files inside `IZO_ASA_UX_SPEC_V4/` plus the directory entry
- machine validation before upload: `user=45 admin=30 total=75`, VALID

## Why the full package is archived here

The repository explicitly forbids a second stable master/roadmap hierarchy. The package is therefore stored as a Git-tracked, checksum-verifiable artifact on this staging branch rather than being dropped wholesale into canonical `docs/` or into frozen PR #36.

The complete archive is preserved unchanged. The files next to it are repository-grounded review artifacts, implementation locators, decision records and lifecycle diagnostics; they are not silently folded into canonical docs.

## Review / implementation documents

- `00_DECISION_REGISTER.md` — established/conflicting/proposed decisions.
- `00_CURRENT_API_MAP.md` — current verified Image/Jobs/Gallery API snapshot.
- `IMPLEMENTATION_GAP_AUDIT.md` — WORKING/PARTIAL/PLACEHOLDER/TARGET-ONLY/CONFLICT audit.
- `UX_V4_TRACEABILITY_MATRIX.md` — requirement → canonical owner → current code owner → test → status traceability.
- `CANONICAL_RECONCILIATION_PATCHSET.md` — exact repository-owned docs that must be reconciled later.
- `IMPLEMENTATION_CONTRACT.md` — bounded implementation rules, safety invariants and required tests.
- `CURRENT_TO_TARGET_FILE_MAP.md` — current source owners/tests for each target UX change.
- `OPEN_DECISIONS.md` — only decisions that remain genuinely unresolved.
- `OWNER_DECISION_PACKET.md` — recommended defaults for O-01…O-08; recommendations only.
- `OWNER_DECISIONS_STATUS.json` — machine-readable O-01…O-08 status snapshot; all remain pending until explicit owner decisions and canonical doc updates.
- `NEXT_PACKAGE_SCOPE_CANDIDATE.md` + `frontend-002-candidate-scope.json` — bounded post-gate Chat reconciliation candidate.
- `FAIL_FIRST_ACCEPTANCE.md` — expected red acceptance cases on the current head.
- `CANONICAL_DOC_PATCH_MANIFEST.md` — section-by-section canonical docs edits.
- `CHAT_PATCH_PREVIEW.md` — minimal exact-source code/copy preview.
- `STAGING_SELF_CHECK.md` — isolation/scope/risk/lifecycle self-check.

## FRONTEND-001 gate / review documents

- `FRONTEND_001_EXIT_GATE.md` — exact remaining gates.
- `FRONTEND_001_VISUAL_AUDIT.md` — second-pass browser-evidence inspection.
- `OWNER_VISUAL_ACCEPTANCE_CHECKLIST.md` — explicit owner review criteria; no acceptance pre-recorded.
- `OWNER_ACCEPTANCE_PACKET_INDEX.md` — short owner-facing index.
- `INDEPENDENT_REVIEW_CHECKLIST.md` — exact-source independent-review checklist; no PASS pre-recorded.
- `FRONTEND_001_GATE_STATUS.json` — machine-readable current gate snapshot.
- `FRONTEND_001_GATE_REQUEST.md` — coordination request without pretending gates are complete.
- `REVIEW_COORDINATION.md` — separation of owner acceptance, independent review, CI and lifecycle repair.

## Lifecycle repair documents

- `LIFECYCLE_NEXT_SELECTION_GAP.md` — proof of the `decides_next + next_package=null` deadlock.
- `PROJECT_STATE_DECIDES_NEXT_PATCH_PREVIEW.md` — fail-closed repair design.
- `ISSUE_188_REPAIR_SCOPE.md` — bounded repair scope/invariants/tests.
- `project-state-188-candidate.json` — machine-readable `MAINT-LIFECYCLE-001` repair candidate, not active state.
- `MAINT_LIFECYCLE_001_ACCEPTANCE.md` — behavioral acceptance contract A-01…A-11 for the repair.
- `PROJECT_STATE_FIX_CODE_SPEC.md` — exact code-change specification preserving strict `transition()` semantics.
- `PROJECT_STATE_FIX_TEST_MATRIX.md` — pure-model/orchestration/CLI regression matrix for issue #188.
- `LIFECYCLE_RECOVERY_PROTOCOL_CANDIDATE.md` — one-time bootstrap proposal for the repair paradox; explicit owner approval required before any use.

## Coverage / archive files

- `coverage_report.md` — coverage summary for 45 user + 30 admin pages.
- `SHA256SUMS.txt` — checksums for the archived v4 source package.
- `restore_ux_v4.py` + `archive/` — exact archive reconstruction path.

## Tracking outside this directory

- PR #36 — FRONTEND-001 exact-source review/acceptance coordination. Review packet links are posted in the PR conversation; neither pending human gate is marked complete.
- Issue #188 — lifecycle continuation deadlock and fail-closed repair.
- Issue #189 — owner decision tracker for O-01…O-08 routes/future studio scope. Checkbox state alone is not canonical; PRODUCT/UX/ARCHITECTURE updates are still required in a permitted package.

## Restore

Run from this directory:

```bash
python restore_ux_v4.py
```

The script reconstructs and verifies the archived v4 source package. After extraction:

```bash
cd IZO_ASA_UX_SPEC_V4
python validate_ux_spec.py
sha256sum -c SHA256SUMS.txt
```

Expected validator result: `UX SPEC VALID`, `user=45 admin=30 total=75`.

## Verification performed

The source implementation and lifecycle tooling were re-read against the frozen source. Review includes shell/Chat, Studio/Jobs/Gallery/Feed/Account/Admin owners, `BLOCK_MAP.json`, `CONTEXT_MAP.json`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `project_state.py`, `project_state_model.py`, `review_evidence.py`, `tests/test_project_state.py`, current shell E2E, PR #36 and exact-head browser evidence.

Current known facts after the latest recheck:

- canonical `ux/frontend-reset` still points to `5c0e79b6fc3a7120207d0889b176fbfed3dab973`;
- PR #36 is still open/draft/unmerged and has 40 changed files;
- all three required exact-head workflows remain recorded as successful;
- owner visual acceptance remains pending;
- independent-review PASS evidence remains pending;
- issue #188 remains the continuation-tooling blocker;
- O-01…O-08 are tracked in issue #189 and remain non-canonical pending explicit decisions.

The browser evidence was unpacked and visually inspected across phone, tablet, laptop, desktop, QHD and UHD. The known visible `Инструменты` Chat picker remains documented as a follow-up mismatch, not as already-fixed behavior.

## Promotion rule

Do not merge this staging artifact directly as canonical product documentation. First close FRONTEND-001 human gates and repair/resolve continuation lifecycle without changing the frozen source. Then reconcile repository-owned `PRODUCT.md`, `UX.md`, `UX_PRODUCT_SHELL.md`, `ADMIN.md`, `ARCHITECTURE.md`/ADR in permitted packages, modify only mapped owners, and rerun exact-source repository checks/CI.
