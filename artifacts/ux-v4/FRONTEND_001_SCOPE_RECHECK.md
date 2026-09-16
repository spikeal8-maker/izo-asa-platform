# FRONTEND-001 — exact 40-path scope recheck

Status: **staging self-audit / not independent review**.

Exact PR/source: #36, `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

A fresh GitHub changed-file query returns exactly 40 paths, matching the declared `cross_domain` hard ceiling. This document rechecks path/sensitive-change shape; it does not replace the required independent reviewer.

## Exact changed paths

```text
apps/web/AGENTS.md
apps/web/e2e/accounts.spec.ts
apps/web/e2e/shell.spec.ts
apps/web/src/features/accounts/AccountPage.tsx
apps/web/src/features/accounts/AuthEntry.tsx
apps/web/src/features/accounts/README.md
apps/web/src/features/accounts/accounts.css
apps/web/src/features/admin/AccessPage.tsx
apps/web/src/features/admin/AccessPanels.tsx
apps/web/src/features/admin/AdminPage.tsx
apps/web/src/features/admin/AdminPanels.tsx
apps/web/src/features/admin/README.md
apps/web/src/features/gallery/AssetPage.tsx
apps/web/src/features/gallery/PrivateImage.tsx
apps/web/src/features/gallery/gallery.css
apps/web/src/features/studio/Composer.tsx
apps/web/src/features/studio/QuoteDialog.tsx
apps/web/src/features/studio/README.md
apps/web/src/features/studio/Studio.tsx
apps/web/src/features/studio/studio.css
apps/web/src/shared/ui/records.css
apps/web/src/shell/App.tsx
apps/web/src/shell/ChatPage.tsx
apps/web/src/shell/SectionPage.tsx
apps/web/src/shell/TopBar.tsx
apps/web/src/shell/chat.css
apps/web/src/shell/layout.css
apps/web/src/shell/navigation.ts
apps/web/src/shell/product-nav.css
apps/web/src/shell/theme.css
docs/BLOCK_MAP.json
docs/CHECKPOINTS.json
docs/CURRENT.md
docs/PLAN.json
docs/UX_PRODUCT_SHELL.md
docs/reviews/FRONTEND-001.md
infra/Caddyfile
tests/test_docs_system.py
tests/test_image_boundaries.py
tools/scopes/frontend-001.json
```

No `apps/api/**`, migration, dependency lock, provider adapter, Credits backend, Jobs backend, Media backend or database runtime file is in the PR diff.

## Sensitive recheck: edge/CSP

`infra/Caddyfile` changes one CSP token only:

```text
img-src 'self' data:
→
img-src 'self' data: blob:
```

Other directives (`default-src`, `script-src`, `style-src`, `connect-src`, `object-src`, `base-uri`, `frame-ancestors`) are unchanged in that patch.

This matches the declared private browser Object URL preview use and does not establish a general remote-image/network relaxation.

## Sensitive recheck: Account/Auth UI

`AccountPage.tsx` retains the existing server calls and handlers and mainly extracts presentation into `AuthEntry.tsx` / `AccountSessions`:

- `/api/v1/auth/me`;
- `/api/v1/auth/sessions`;
- `/api/v1/guest/me`;
- guest claim vs login/register endpoint choice;
- session/logout revoke behavior;
- CSRF is still passed for guest claim and session mutations.

The patch does not introduce a client-side role/identity bypass. The extracted presentation receives typed auth/session state and callbacks rather than reimplementing the transport.

## Sensitive recheck: Admin/Access UI

`AdminPage.tsx` extracts navigation/search/detail/audit presentation into `AdminPanels.tsx`; existing server-loading/search/credit-refresh orchestration stays in `AdminPage.tsx`.

`AccessPage.tsx` extracts lookup/subject form presentation into `AccessPanels.tsx`. The mutation function, server endpoint construction, operation-id handling, current-password handling and server response remain in the existing owner page rather than moving into generic shell code.

The diffs do not add a client-side permission source of truth. Visibility remains based on server-returned permissions and backend authorization remains authoritative.

## Sensitive recheck: paid Image admission

`Composer.tsx` is a newly extracted owner in this PR, but its current exact-source implementation explicitly retains:

- server `GET /api/v1/entitlements` policy;
- server Credits loading;
- expiring server quote from `POST /api/v1/jobs/quotes`;
- persistent `Pending` state via `remember(account.id, quote.id)`;
- stable `operation_id` submitted with `quote_id`;
- `rejectedBeforeAdmission` distinction;
- preservation of pending id for unknown outcome;
- blocking submit if pending-state storage cannot be safely read/written;
- server Job handoff to `/jobs/{id}`.

Thus the frontend split does not replace server price/admission truth with local calculation. Exact-head studio/provider CI is still the primary behavioral evidence; this staging audit only confirms the source shape.

## Shell/product surface

The shell changes are concentrated in `App.tsx`, `ChatPage.tsx`, `TopBar.tsx`, navigation, semantic theme and split layout/product-nav/chat styles. No Chat backend endpoint is introduced. The local Chat user turn ends in an explicit unavailable-runtime note, not a fake model result.

Known product mismatch remains: visible manual `Инструменты` picker is in the exact frozen source and is intentionally targeted by the bounded follow-up Chat reconciliation.

## Documentation/process paths

PLAN/CURRENT/CHECKPOINTS and FRONTEND-001 scope/review docs are part of this already-frozen package state. No staging v4 document has been inserted into the PR or canonical branch.

## Scope verdict

**SELF-AUDIT PASS FOR PATH/SENSITIVE-DIFF SHAPE.**

- exact count = 40;
- no backend runtime/business source in diff;
- CSP delta is narrow;
- Account/Admin/Access changes are primarily presentation extraction around existing server-owned logic;
- Image admission safety remains explicit in the extracted Composer;
- no conclusion here satisfies the independent-review gate.
