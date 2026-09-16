# IZO ASA UX v4 — canonical document patch manifest

Status: **staging / patch manifest**. This is a precise editing map for the next bounded package; it does not itself modify canonical docs.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. `docs/PRODUCT.md`

### Current conflict

The v0.2 page registry still contains older information architecture assumptions: U-01 assigns `/` to a general main page, U-09 defines `/app` as a workspace hub, and U-15/U-16 define `/chat` + `/chat/{threadId}` before the Chat backend exists.

### Patch intent

Do not rewrite the whole page registry. Add a short reconciliation note near the route/page-contract introduction and adjust only conflicting rows/wording so the document distinguishes:

- **current accepted frontend entry:** `/` = Chat-first surface;
- **current compatibility alias:** `/studio/chat`;
- **current working direct studio:** `/image` plus current `/studio/image` compatibility;
- **unresolved/future:** durable `/chat/{threadId}`, `/paint`, concise Video/Audio/3D migration;
- `/app` is not to be implemented as a second creative dashboard merely because the older target registry contains it.

Do not remove target capabilities P-01..P-12 or the U-ID registry. Preserve the distinction between target behavior and current implementation.

### Acceptance text

A reader must not conclude from PRODUCT that:

1. `/` is still Feed/marketing-first;
2. `/app` must be built now;
3. `/chat` already has durable server threads;
4. `/video`, `/audio`, `/3d` already work merely because target rows exist.

## 2. `docs/UX.md`

### Current conflict

Section 2 says exact routes and the first page after login are not yet approved. That is stale relative to active Chat-first `FRONTEND-001`, while several secondary route decisions really are still pending.

### Patch intent

Replace the broad uncertainty with a split statement:

- confirmed/current owner direction: Chat-first `/`, direct Image, separate Feed/Gallery;
- current compatibility aliases are implementation details and not new product destinations;
- pending decisions: Video/Audio/3D canonical route migration, durable ChatThread URLs, Image editor route;
- phone remains the same product/business logic with transformed layout.

Keep the existing viewport, accessibility, state-matrix and resource-budget requirements intact.

## 3. `docs/UX_PRODUCT_SHELL.md`

### Current conflict

Section 1 currently says Chat is an ordinary dialog plus launch of Image/Video/Audio/3D "из одного composer". Current `ChatPage.tsx` interpreted this as a visible `Инструменты` workspace picker.

### Patch intent

Replace only the semantic contract, not geometry/colors:

- Chat is **intent-driven**;
- user writes natural-language intent;
- future orchestrator chooses allowed capability internally;
- direct manual controls stay in top-level Image/Video/Audio/3D Studios;
- composer = message + `+` attachment/context + mic + send;
- no persistent workspace/tool catalog inside Chat;
- until CHAT backend exists, no fake assistant/tool success.

In section 8 acceptance add an explicit regression item: Chat home has no persistent `Инструменты` picker for choosing creative workspaces.

Preserve 260px sidebar, 56px header, 768px chat/composer measure, mobile two-row top area, Semantic Color System v1.1 and the viewport matrix.

## 4. `docs/ADMIN.md`

Not required in the first bounded Chat package unless a docs test would otherwise continue to imply that every A-01..A-30 screen is implemented. Preferred default: **do not touch ADMIN.md in FRONTEND-002 candidate**. The current gap is recorded in staging and can be reconciled in a later admin/docs package.

Reason: adding unrelated admin target/current cleanup would expand a focused Chat shell package without changing the user result.

## 5. `docs/ARCHITECTURE.md`

No change in the first bounded Chat package.

The architecture already lists target `ChatThread/Message` and `ChatRequest/ToolInvocation` as future logical entities. Do not create tables/API/runtime or an ADR merely to support presentation copy. Architecture changes belong to `CHAT-001` when durable server behavior is actually implemented.

## 6. `docs/BLOCK_MAP.json` / `docs/CONTEXT_MAP.json`

Default: no change unless implementation changes ownership or current routing fails to locate the affected block after wording changes.

Existing ownership already points shell/Chat work to `ChatPage.tsx`/shell and Studio to its own feature. Do not add future Video/Audio/3D blocks before real owners exist.

If a new block locator is justified, it should be narrow, e.g. Chat composer controls, with `ChatPage.tsx` owner and `shell.spec.ts` as nearest test. Do not broaden `web.shell` initial context.

## 7. `apps/web/AGENTS.md`

Default: no change. It already identifies `ChatPage.tsx` + `chat.css` as the Chat owner and explicitly says working Image generation remains in `features/studio`.

Only update it if implementation changes ownership, not for copy-only semantics.

## 8. Review document

The future package review should record:

- exact source/base and scope class;
- the two fail-first cases and why they were red;
- changed files with bytes/lines/headroom;
- confirmation that Image/Jobs paid-safety paths were not modified;
- shell/browser viewport evidence;
- docs/context budget delta;
- final exact-head CI and owner visual acceptance state.

## 9. Forbidden patch behavior

- no wholesale replacement of PRODUCT/UX with the staging master spec;
- no new `MASTER_PLAN`, `ROADMAP`, `NOW` or second product registry;
- no mutable SHA/PR in stable canonical docs;
- no route redirect implemented before route decision;
- no backend entity/API invented by UX copy;
- no unrelated Admin/Gallery/Studio refactor "for consistency".

## Self-review

PASS: every proposed canonical edit has one existing repository owner, changes only the conflicting statement, preserves target/current distinction, and avoids expanding the first implementation package beyond Chat-first reconciliation.