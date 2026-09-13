# CATALOG-002 · self-review

Base checkpoint: SETTINGS-002 `220d302dc238889da066c1799652d4b036007de3` / PR #30.
Implementation is re-authored from provider-neutral lessons in historical PR #20; no OpenRouter runtime code was cherry-picked.

## Implemented boundary

- staff-only immutable capability and connection revisions;
- code-owned provider/adapter registry with canonical fal endpoint;
- opaque credential locator metadata, fresh-password bind/rotate/revoke, no raw key response;
- offline contract proof bound to exact capability/connection hashes and credential version;
- publish keeps connection `disabled`; capability reports `runtime_available=false`;
- idempotent operation receipts, optimistic versions and PostgreSQL immutable history;
- migration `0011_catalog` from canonical `0010_access`;
- no change to current Jobs/Fal execution or provider-call recovery.

## Findings fixed during self-review

1. Removed inherited `price_credits`, `spend_cap_minor`, `allow_fallbacks` and `resolutions`: they would duplicate Jobs/Entitlements/Fal/pricing ownership and bypass a future `pricing.write` boundary.
2. `save_revision()` now uses the existing nested atomic guard so concurrent first-create unique conflicts become safe `catalog_conflict`, not raw SQL errors.
3. PostgreSQL acceptance now includes both initial-create and existing-head version races.
4. CATALOG-UI dependency was corrected to `CATALOG-002 + ADMIN-001 + ACCESS-001`; stale UX-001 design acceptance no longer blocks the admin catalog path.
5. Low-token routing now has `api.catalog` plus capability/connection/credential/proof/publish block locators; generic same-route block ambiguity safely falls back to the route.

## Local verification before freeze

- CATALOG domain + migration tests: PASS.
- Locked Linux Python 3.13 CATALOG domain/HTTP/migration: **25/25 PASS**.
- Cross-package Access/Settings/Jobs/Media/Admin boundary selection: PASS.
- docs checker and project-state verifier: PASS.
- pinned Python 3.13 OpenAPI export/check: exact PASS.
- openapi-typescript, TypeScript and Vite production build: PASS.
- `py_compile` and `git diff --check`: PASS.

Windows TestClient is not treated as an HTTP gate because the repository-wide unit socket ban intercepts asyncio `socketpair()` before a request is created; locked Linux tests are the HTTP evidence.

## Remaining acceptance

GitHub Foundation CI must still prove the real PostgreSQL race, immutable triggers, isolated ACCESS provisioning/cleanup, Compose restart persistence and that later ACCESS/JOBS/IMAGE acceptance remains green.
No fal key, provider network call or external spend is part of CATALOG-002.

**SELF_REVIEW PASS · FULL GITHUB CI REQUIRED · MERGED NO · DEPLOYED NO**
