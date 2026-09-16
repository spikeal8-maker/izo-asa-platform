# IZO ASA UX v4 — current → target file map

Статус: **staging / implementation locator**. Назначение — дать coding-agent минимальный набор owner-файлов и тестов для конкретной UX-правки. Не является `BLOCK_MAP.json` и не заменяет его.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. Shell и Chat

| Target change | Current source owner | Support | Nearest tests | Backend dependency |
|---|---|---|---|---|
| Убрать ручной workspace picker из Chat | `apps/web/src/shell/ChatPage.tsx` | `chat.css` | `e2e/shell.spec.ts` | none; presentation-only |
| `+` = attachment/context entry | `ChatPage.tsx` | shared UI only if reused | `e2e/shell.spec.ts` | upload/media only when actually implemented |
| Chat wording = intent-driven | `apps/web/src/shell/navigation.ts`, `docs/UX_PRODUCT_SHELL.md` | `TopBar.tsx` | `e2e/shell.spec.ts`, docs tests | CHAT runtime not required |
| Help no longer says “выберите инструмент” | `apps/web/src/shell/SectionPage.tsx` | none | `e2e/shell.spec.ts` | none |
| Alias/canonical route normalization | `apps/web/src/shell/App.tsx`, `router.tsx`, `navigation.ts` | `TopBar.tsx` | `e2e/shell.spec.ts` | none unless introducing durable deep links |

Current contradiction: `ChatPage.tsx` owns both `+` and a second `Инструменты` control, while UX v4 requires `+` for context and top-level navigation for direct Studios.

## 2. Image Studio

| Target change | Current owner | Safety owner that must stay intact | Nearest tests |
|---|---|---|---|
| New studio geometry/layout | `apps/web/src/features/studio/Studio.tsx`, `studio.css` | `Composer.tsx` admission semantics | `e2e/studio.spec.ts` |
| Prompt/model/size restyle | `Composer.tsx`, `studio.css` | `/api/v1/entitlements`, quote contract | `studio.spec.ts`, `provider.spec.ts` |
| Quote dialog redesign | `QuoteDialog.tsx` | quote id/expiry + exact submit | `studio.spec.ts` |
| Result presentation redesign | `ResultPanel.tsx`, `studio.css` | server Job state, asset id, charged/reserved credits | `studio.spec.ts`, `provider.spec.ts` |
| References/source picker | new bounded Studio child + existing Media/API contracts | ownership/type/size validation | new targeted tests + existing media boundaries |
| Edit/mask/outpaint | future IMAGE-002 owners | never overwrite original Asset; capability gate | separate package tests |

Do not move quote/idempotency/unknown-response logic into visual components or duplicate it for desktop/mobile.

## 3. Jobs

Current owner: `apps/web/src/features/studio/ResultPanel.tsx`.

Target UI may separate list/detail presentation into smaller files if size/headroom requires it, but these semantics stay server-owned:

- active polling;
- `reconciliation_required`;
- `provider_submission_unknown`;
- `provider_auth_required`;
- `provider_deadline`;
- cancel request versus confirmed terminal result;
- reserved versus charged credits;
- successful `asset_id` handoff to Gallery.

Nearest tests: `e2e/studio.spec.ts`, `e2e/provider.spec.ts`, plus backend Jobs/provider safety suites for semantic changes.

## 4. Gallery / Asset

| Target change | Current owner | Nearest tests | Boundary |
|---|---|---|---|
| Gallery grid/layout | `features/gallery/Gallery.tsx`, `gallery.css` | `e2e/gallery.spec.ts` | list remains private/current-account only |
| Private preview | `PrivateImage.tsx` | `gallery.spec.ts` | authenticated bounded bytes/object URL cleanup |
| Asset detail actions | `AssetPage.tsx` | `gallery.spec.ts` | server ownership checked per action |
| Multimodal card/viewer | future shared media presentation component | modality package + gallery tests | do not fetch full originals for grid |
| Delete/publish | future explicit Media/Feed commands | new tests | dependency/Publication state must be server truth |
| Lineage/version UI | future Asset detail child | new tests | derived relation must exist in backend contract first |

## 5. Feed

Current owner: `features/feed/FeedPage.tsx` + `feed.css`.

Current state is presentation-only editorial examples. A visual change may adjust layout/copy, but real author/like/publication objects cannot be introduced as fake local data.

When FEED runtime exists, likely owner split should separate feed list, publication detail and publish/unpublish dialog rather than expand the existing page indefinitely.

## 6. Account / Auth

| Surface | Current owner | Current server truth | Tests |
|---|---|---|---|
| Login/Register/Account/Sessions | `features/accounts/AccountPage.tsx`, `AuthEntry.tsx` | auth/me, sessions, revoke, guest claim | `accounts.spec.ts`, `guest.spec.ts` |
| Verify/forgot/reset/change | `SecurityPage.tsx` | challenge/password lifecycle | `email-security.spec.ts` |
| Connections | `SecurityPage.tsx` | email/password state only | `email-security.spec.ts` |

Shell/visual work must not alter CSRF, fresh-auth, challenge, revoke or guest claim semantics. Telegram/MAX linking is not implemented merely because the product spec contains those pages.

## 7. Credits

Current owner: `features/credits/CreditsPage.tsx`.

Use server `available/reserved/history`; do not rename product Credits into LLM token counts or synthesize daily/monthly buckets unless backend contract explicitly introduces them.

Nearest test: affected account/studio specs; semantic changes also require Credits backend tests.

## 8. Admin

| Current working subset | Current owner | Nearest tests |
|---|---|---|
| Admin landing/users/search | `features/admin/AdminPage.tsx`, `AdminPanels.tsx` | `e2e/admin.spec.ts` |
| User detail + allowed credit view/action | `AdminPanels.tsx`, `GrantForm.tsx` | `admin.spec.ts` |
| Audit | `AdminPage.tsx`, `AdminPanels.tsx` | `admin.spec.ts` |
| Access delegation | `AccessPage.tsx` | `e2e/access.spec.ts` |

A-01…A-30 remain target registry. Do not create blank route components for all targets. Each new admin area appears with its domain package, permission contract, owner README/block locator and tests.

## 9. Placeholder Studios

Current Video/Audio/3D owner is not a feature module: generic preview cards live in `apps/web/src/shell/SectionPage.tsx` for `/studio/video`, `/studio/audio`, `/studio/3d`.

When a modality becomes real:

1. create a bounded feature owner under `apps/web/src/features/<modality>/`;
2. add a short local README with routes/invariants/tests;
3. add narrow `CONTEXT_MAP`/`BLOCK_MAP` entries;
4. route App/shell to the feature owner;
5. remove only that modality’s generic `SectionPage` placeholder;
6. keep unsupported modes honest until their backend capability exists.

Do not build one universal mega-Studio component for Image/Video/Audio/3D: they share infrastructure and tokens, not identical interaction models.

## 10. Shared components allowed to emerge

Extract a shared component only when at least two real owners need the same behavior, not because UX v4 lists a conceptual component.

Safe candidates once repetition exists:

- model/capability picker;
- source/asset picker;
- quote/confirmation frame;
- job status display;
- media viewer shell;
- responsive history rail;
- admin list/detail frame.

Business logic stays in domain owners; shared UI receives typed state/actions and does not own Credits, provider selection or Media authorization.

## 11. Self-review

PASS as a locator:

- every current owner named here was verified in the active frontend tree;
- placeholders are not promoted to runtime features;
- no new backend API path is asserted;
- exact current Image/Jobs/Auth/Admin semantics are referenced rather than reimplemented;
- extraction guidance respects existing file/context/headroom rules.
