# GUEST-001 · SELF REVIEW

- Base: `731105b1c8d16d9774c987a31b62ee7143383ccc` (MAINT-SIZE-001)
- Branch: `feat/guest-trial`
- Requested `до → после`: login wall before first use → one bounded image trial before registration, then same-owner registration claim.
- Scope: Accounts guest principal, trial accounting, one Jobs admission hook, guest HTTP/UI, migration/tests/CI/docs only.
- Live provider spend: **none**. Guest capability is deliberately `test.image.v1` in this package.

## Critical review

1. **Acceptance**
   - Anonymous visitor gets a server-owned guest principal without a normal account session.
   - Exactly one new guest generation operation is admitted; exact operation replay remains idempotent.
   - Registration adds email/password to the same `accounts.id`; Jobs/Media/Credits are not copied.
   - Active job blocks claim until terminal state.

2. **Scope**
   - No Catalog/Admin/Fal transport changes.
   - Existing Jobs worker, Media storage and Entitlements remain the runtime path.
   - Guest-specific source files remain below repository modularity limits.

3. **Security / abuse**
   - Guest bearer is stored in a separate table and cannot authorize `/api/v1/auth/*` account surfaces.
   - Mutations require current same-origin + CSRF rules.
   - Owner, price, budget and provider are never accepted from client input.
   - Guest creation is HMAC-keyed network-rate-limited and the session expires.
   - External capability requests are rejected by GUEST-001.

4. **Credits / idempotency**
   - Trial credit is a distinct bounded internal ledger movement (`trial` / `guest_trial`), no fake staff actor.
   - Database constraints and deterministic operation ID make trial issuance auditable and one-time per guest owner.
   - Jobs admission guard runs in the same transaction as output/credit reservation.

5. **Persistence / claim**
   - PostgreSQL/S3 acceptance is wired to create a guest, execute the existing test-image worker, restart Compose, re-read the same job/asset, then claim the same owner.
   - Normal auth after claim must see the same job, asset and wallet state.

6. **Web / responsive**
   - Studio uses `GuestTrial` only when normal auth is absent.
   - Refresh recovers guest job state from the server.
   - Registration detects an active guest and calls `/guest/claim` instead of creating a second account.
   - Result image is width-bounded for mobile/wide layouts.

7. **Contracts / docs**
   - Migration `0011_guest`, OpenAPI snapshot, local Guest README, CONTEXT_MAP, PLAN/CURRENT and MAINT checkpoint are updated.
   - Router corpus contains guest frontend/backend phrases.

## Known non-goals / follow-up

- GUEST-001 does **not** spend money or call fal.ai. A real external-AI free trial requires explicit provider-spend approval and live provider acceptance.
- Expired unclaimed guest rows/results become inaccessible but long-term deletion/retention is not implemented here; that belongs with account-data/operations retention policy and must be tracked before public launch.
- Existing-account login does not merge an anonymous owner into a different existing account; same-owner claim applies to new registration only.

## Verdict

`PASS` for the defined GUEST-001 scope, contingent on final required GitHub workflows including PostgreSQL/S3 restart acceptance.

Next action: run full CI on the final tree; fix only concrete gate failures, then freeze the source head.
