# IZO ASA UX v4 — candidate scope for the next package

Status: **staging / candidate only**. This is not `PLAN.json`, does not activate a package, and must not be used as a substitute for `project_state.py begin-next`.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

Candidate ID: `FRONTEND-002` only as a working name until the normal lifecycle transition assigns/accepts the next package.

## Goal

Reconcile the repository-owned Chat-first product/UX contract and make the current Chat presentation match it, without introducing any new backend runtime and without migrating unresolved Video/Audio/3D/ChatThread/Image-editor routes.

### Before

- `/` is already Chat-first in the current frontend.
- `ChatPage.tsx` still exposes a manual `Инструменты` picker for Image/Video/Audio/3D.
- Help tells the user to choose a tool from Chat.
- `UX_PRODUCT_SHELL.md` says Chat launches Image/Video/Audio/3D "из одного composer", which is ambiguous and supports the wrong manual-tool mental model.
- `PRODUCT.md` and `UX.md` still contain older route/entry assumptions that need explicit reconciliation rather than silent router changes.

### After

- repository-owned docs state Chat = intent-driven conversation and Studios = direct tool-driven control;
- Chat composer has message input + attachment/context `+` + mic + send, with no persistent workspace/tool picker;
- Help/navigation wording no longer teaches manual tool selection inside Chat;
- current Image/Jobs/Gallery/Auth/Admin runtime semantics are unchanged;
- unresolved route decisions remain explicitly unresolved.

## Scope class / risk

- proposed scope class: `normal` (target <= 20 paths);
- proposed risk: `medium` because this is shell/docs/presentation work and does not alter auth, permissions, Credits, provider paid lifecycle, migrations, secrets, or cross-account access;
- owner visual acceptance remains required for the resulting shell;
- if actual implementation expands into high-risk semantics, the scope/risk must be reclassified before code changes.

## Candidate allowed paths

Lifecycle/state files created or updated only by the normal package transition:

- `docs/PLAN.json`
- `docs/CURRENT.md`
- `docs/CHECKPOINTS.json`
- `tools/scopes/frontend-002.json` (candidate name)

Canonical docs:

- `docs/PRODUCT.md`
- `docs/UX.md`
- `docs/UX_PRODUCT_SHELL.md`
- `docs/reviews/FRONTEND-002.md` (candidate name)

Frontend owners:

- `apps/web/src/shell/ChatPage.tsx`
- `apps/web/src/shell/chat.css`
- `apps/web/src/shell/navigation.ts`
- `apps/web/src/shell/SectionPage.tsx`

Tests/doc guards:

- `apps/web/e2e/shell.spec.ts`
- `tests/test_docs_system.py` only if needed to prevent regression of the canonical wording/route contract
- `tests/context_cases.json` only if routing examples become stale after the wording change

Target: 15 paths maximum if all optional guards are required; do not expand the package to unrelated Studio/Gallery/Admin implementation.

## Explicit non-goals

- no `App.tsx`/`router.tsx` route migration in this package;
- no canonical `/video`, `/audio`, `/3d` decision;
- no `/chat/{threadId}` implementation;
- no `/paint`/Image editor route decision;
- no Chat backend, threads, messages, streaming, orchestration or tool execution;
- no Video/Audio/3D backend or feature modules;
- no Feed Publication backend;
- no Image quote/admission/provider/Jobs semantics change;
- no Credits/Auth/permissions/Media ownership change;
- no merge/deploy/live provider call.

## Invariants

1. Existing Image Entitlements -> quote -> stable operation ID -> Job -> Media flow remains untouched.
2. Unknown paid submit outcome is never converted into a second operation.
3. Chat without server runtime never renders assistant/tool success.
4. Top-level creative navigation still exposes Chat/Image/Video/Audio/3D.
5. Current placeholder Video/Audio/3D surfaces remain honest placeholders.
6. Feed examples remain explicitly non-user publications.
7. Current auth/session/admin permission checks are not changed by shell copy work.
8. Semantic Color System v1.1 and responsive shell geometry remain intact unless owner-approved visual review changes them explicitly.

## Required lifecycle preconditions

`FRONTEND-001` cannot be bypassed. Before this candidate can become active, the repository's normal gate must succeed for the current frozen source head. PR #36 currently has technical CI evidence, but remains draft and requires the package's remaining acceptance/review gates. `begin-next` is the only permitted state transition.

## Self-review

PASS as a bounded candidate: the proposal has a finite path list, explicit non-goals, no backend invention, no silent route migration, and preserves all currently verified paid/security boundaries.