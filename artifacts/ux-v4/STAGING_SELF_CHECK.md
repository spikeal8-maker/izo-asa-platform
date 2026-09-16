# IZO ASA UX v4 — staging self-check

Status: **verified staging review**. This document records the second-pass checks performed after the bounded next-package artifacts were added. It is not canonical project state.

Verification source: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. Canonical branch isolation

Verified after the staging writes:

- `ux/frontend-reset` still points to `5c0e79b6fc3a7120207d0889b176fbfed3dab973`;
- staging branch is descended from that exact source head;
- compare reports staging **ahead only**, with no canonical branch rewrite;
- every staging diff path is under `artifacts/ux-v4/`;
- `docs/PLAN.json`, `docs/CURRENT.md`, canonical PRODUCT/UX/ADMIN docs and runtime source were not changed on `ux/frontend-reset`.

This confirms the preparation work did not mutate the frozen `FRONTEND-001` source.

## 2. Candidate scope arithmetic

`frontend-002-candidate-scope.json` contains 15 candidate paths against a `normal` hard ceiling of 20.

The list includes three lifecycle state files and the future scope/review files because a real `begin-next` transition/package would need them. Two test-support paths are explicitly optional and require justification before use.

Result: **scope headroom = 5 paths** before the normal ceiling. The candidate must not consume that headroom for unrelated cleanup.

## 3. Risk classification check

Proposed `risk=medium` is consistent only while the package remains presentation/docs work:

- no Auth semantics;
- no permissions/access mutation;
- no Credits/financial semantics;
- no migration;
- no provider paid lifecycle;
- no credentials/secrets;
- no cross-account access;
- no release/network policy.

If implementation crosses any of those boundaries, the package must be reclassified before the code change and the high-risk independent-review gate becomes mandatory for that package as well.

## 4. Fail-first cases verified against current source

### Expected red A-01

Current `ChatPage.tsx` contains:

- a visible `Инструменты` button;
- a `chat-tools-popover`;
- Image/Video/Audio/3D workspace links inside that popover.

Therefore the proposed assertion `button[name=Инструменты] count == 0` is expected to fail on the frozen source for the intended reason.

### Expected red A-04

Current Help copy in `SectionPage.tsx` contains `выберите инструмент` in the Chat guidance.

Therefore the proposed Help assertion rejecting that phrase is expected to fail on the frozen source for the intended reason.

### Existing green guards

Current `shell.spec.ts` already proves Chat-first `/`, `/feed` separation, five creative modes on mobile, theme persistence, Jobs not being primary navigation, platform-hint non-authentication, and responsive/8K shell behavior. The new tests extend that suite rather than replacing it.

## 5. Server-truth preservation check

The candidate scope excludes the current Image Studio/Jobs implementation owners except for regression test execution. No proposed code path touches:

- `Composer.tsx` quote or submit logic;
- stable `operation_id` persistence/replay;
- `ResultPanel.tsx` provider uncertainty/reconciliation semantics;
- Media ownership/loading;
- Credits ledger/reserve/settle;
- Auth/session/CSRF;
- Admin permission enforcement.

Result: **no paid/security semantic rewrite is required to obtain the Chat UX result**.

## 6. Route-decision check

The candidate deliberately does not edit `App.tsx` or `router.tsx` and does not resolve:

- `/video` vs `/studio/video`;
- `/audio` vs `/studio/audio`;
- `/3d` vs `/studio/3d`;
- durable `/chat/{threadId}`;
- `/paint` vs integrated/nested Image editor.

This prevents a documentation cleanup from becoming a route migration package.

## 7. Current lifecycle blocker

PR #36 remains draft/unmerged on the frozen source. Its package is high-risk and the current PR conversation has no independent-review evidence comment. The staging candidate therefore **must not** be activated by manually creating a canonical continuation branch. Normal `project_state.py begin-next` remains the gate after all required `FRONTEND-001` evidence/acceptance conditions are satisfied.

## 8. Documentation consistency check

The new artifacts are layered rather than competing sources of truth:

- `OPEN_DECISIONS.md` = unresolved choices only;
- `CANONICAL_DOC_PATCH_MANIFEST.md` = exact future canonical doc edits;
- `NEXT_PACKAGE_SCOPE_CANDIDATE.md` + JSON = bounded candidate scope;
- `FAIL_FIRST_ACCEPTANCE.md` = red/green acceptance contract;
- `CURRENT_TO_TARGET_FILE_MAP.md` = source owners/tests;
- `IMPLEMENTATION_CONTRACT.md` = semantic and safety boundaries.

Canonical ownership remains PRODUCT/UX/ADMIN/ARCHITECTURE as defined by the repository documentation system.

## Verdict

**PASS — staging preparation is bounded, isolated from the frozen source, fail-first cases are grounded in current code, unresolved routes remain unresolved, and the proposed first implementation does not require backend/paid/security changes.**
