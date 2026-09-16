# 00E — Current Implementation / API Map

This file records a **snapshot**, not a stable product contract. Verified against `spikeal8-maker/izo-asa-platform` branch `ux/frontend-reset` at head `5c0e79b6fc3a7120207d0889b176fbfed3dab973` on 2026-09-16. Re-fetch before implementation because repository source of truth may move.

## Current Image flow observed

| UI responsibility | Current endpoint / mechanism | Current invariant to preserve |
|---|---|---|
| Entitlement/policy | `GET /api/v1/entitlements` | Sizes/capabilities/executor availability come from server policy. |
| Credits | `GET /api/v1/credits` | UI separates available balance from later reserve/settle lifecycle. |
| Quote | `POST /api/v1/jobs/quotes` | Current payload includes capability, prompt, width, height; quote expires. |
| Paid/test submit admission | `POST /api/v1/jobs` | Uses `quote_id` + client-persisted `operation_id` for safe replay/idempotency. |
| Unknown submit outcome | pending operation persisted client-side | Do not issue a different paid submit; replay/reconcile the same operation or inspect Jobs. |
| Success transition | navigate to `/jobs/{jobId}` | Job detail is operational truth; later result belongs in Gallery. |
| Gallery list | `GET /api/v1/media/assets?limit=20&offset=…` | Private server-owned assets with paging/storage accounting. |

## Current owner files observed

- `apps/web/src/features/studio/Composer.tsx` — quote/submission safety and current Image form.
- `apps/web/src/features/studio/QuoteDialog.tsx` — current confirmation.
- `apps/web/src/features/studio/ResultPanel.tsx` — current result rendering owner.
- `apps/web/src/features/gallery/Gallery.tsx` — current private asset list.
- `apps/web/src/features/gallery/AssetPage.tsx` / `PrivateImage.tsx` — current asset detail/private image path.
- `apps/web/src/shell/App.tsx` — current route composition.
- `apps/web/src/shell/ChatPage.tsx` — current transitional Chat UI.
- `apps/web/src/shell/navigation.ts` / `TopBar.tsx` — current creative navigation.

## Mandatory preservation rule

A visual rewrite of Image must not regress quote expiry, server-owned capability policy, operation-id replay, rejected-before-admission distinction, unknown-outcome handling, CSRF/session enforcement, or private Asset ownership. A replacement UI must call the same safe domain path until an explicit backend package changes that contract.

## API honesty rule for future studios

Video/Audio/3D/Chat tool execution endpoints are **not specified here unless verified in the current branch**. UX may describe target states, but implementation must not fabricate successful runtime, fake prices, fake progress or local-only persistence.
