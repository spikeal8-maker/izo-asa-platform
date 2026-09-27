# ADMIN-DONOR-CATALOG-001 · implementation contract

## Before → after
Before: Admin is reachable only from admin pages; DeepSeek Chat exposes two fixed models without a product price, and the donor IZO_ASA Admin architecture is documented only outside the canonical line.
After: authorized staff can open Admin from the top bar between 3D and tokens, inspect and update a versioned catalog of approved existing text/image models and explicit RUB display prices; Chat lists only published enabled text models with those server-owned prices and rechecks the choice on admission. Unknown price is shown as unknown, never free.

## Fixed scope
- Package/base: `ADMIN-DONOR-CATALOG-001` from `feat/chat-deepseek-001@d2d1d76ea86193dea1d83b0371c56216d0247dfb`.
- Donor source: `spikeal8-maker/IZO_ASA@93a0a9d4bef1b478030788700e4c2241d9ef1cca`; copy taxonomy and acceptance scenarios, not code or historical price values.
- First catalog covers only server-approved IDs with existing runtime support: DeepSeek text models and existing image capability metadata. No dynamic provider URL, API key, new transport or OpenRouter execution.
- Price units are integer kopeks per million input/output text tokens and per approved image model. Values may be unset; unset is not zero. Display prices are informational and do not mutate the existing Credits ledger or Jobs charge. Existing DeepSeek BYOK preview may run with an unknown displayed price because the user supplies the provider key and no platform Credits are debited; the UI must not imply that the external provider is free. Platform-funded paid runtime must require a complete approved price and quote in a later package.
- Staff reads require `catalog.read`; publication/config changes require `catalog.write`; price changes additionally require `pricing.write`. Each mutation uses an expected revision and durable audit. Browser permission hints never authorize the backend.
- Frontend Admin entry stays in the shared top bar; the catalog page has its own permission-correct endpoint so catalog-only staff do not depend on `/api/v1/admin/me` (`users.read_limited`). Mobile layout and direct navigation remain usable.
- An already enrolled local access owner can explicitly add the newly introduced `pricing.write` permission and matching delegation ceiling through a guarded operator procedure; migration and application startup never grant it automatically.

## Risk and acceptance
Risk: high, because staff permissions, model admission and visible financial semantics change. Nearest failing cases before implementation: non-staff/catalog-only access; unknown price ≠ free; stale revision conflict; unapproved model rejection; disabled model admission; repeated mutation; existing owner upgrade without automatic grant; 320px top-bar collision and catalog pricing visibility; model price after refresh. Verify migration on isolated PostgreSQL, targeted API/E2E tests, self-review, full required CI and exact-SHA independent review or explicit owner waiver before technical acceptance.

## Non-goals
No new ledger, billing or paid live calls; no arbitrary provider/model execution; no Chat sidebar redesign; no merge/deploy/release.

## Implementation self-review

Verdict: `PASS` for the scoped implementation; technical acceptance remains pending full required CI and exact-SHA independent GitHub review or an owner waiver for this package. The catalog reuses Accounts staff grants and Chat admission, while Credits, Jobs, Media and provider credentials remain their existing owners. The browser displays prices but cannot authorize a model, set a price without `pricing.write`, or cause a charge. A disabled model is rejected for a new request; a previously accepted request replays against its stored model revision. Unknown price stays distinct from explicit zero, and BYOK preview explains that the external provider may charge separately. Image metadata remains unpublishable until the Jobs path is bound.

Negative/refresh/race evidence: local domain/architecture suite `78 passed`; frontend build and targeted laptop/320px browser suite `26 passed, 4 skipped`; isolated PostgreSQL 17 applied migration `0013_admin_catalog` with three seed models, and the env-gated migration/CAS/Chat-admission/restart test passed six consecutive runs against a disposable schema. No real provider key, paid call or production network was used. Windows TestClient HTTP cases remain blocked by the existing unit socketpair guard and are assigned to Linux CI.

Maintainability delta: finite cross-domain scope `40/40`, no outside or unapproved sensitive paths. New `api.catalog` route starts at 4,188 bytes; local Markdown is 2,170 bytes in Catalog, 2,591 in web Admin and 926 in Chat. Largest changed production files: `ChatComposer.tsx` 9,496 bytes, `TopBar.tsx` 9,480, Chat `conversations.py` 9,124, Catalog `service.py` 8,184 and `ChatComposer.css` 9,380; all stay below the 80%-of-hard-limit warning. The new browser cases live in `catalog.spec.ts` (6,876 bytes), leaving existing `shell.spec.ts` unchanged. PLAN is 9,236 bytes after shortening historical descriptions without removing package state, below its 10 KB context gate. Generated OpenAPI is the only generated diff; no lockfile, key or dependency changes. New catalog/API and web Admin owners have short local READMEs and targeted context routes. The next catalog edit should split `service.py` only when its owner grows; this package did not raise any file/context limit.

Open limits after this slice: no OpenRouter adapter/connection controls, provider-cost/FX freshness, image mode pricing, platform-funded quote or Credits settlement. The existing local ACCESS owner needs an explicit isolated upgrade for `pricing.write`; migration does not grant it automatically. The broader ChatGPT-style sidebar and multimodal image flow remain separate packages.
