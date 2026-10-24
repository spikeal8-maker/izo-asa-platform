# P0-B1 — Admin-managed DeepSeek registry: implementation evidence

## Result and explicit limits

Server-side encrypted platform DeepSeek configuration is stored separately from personal BYOK.
Admin can replace, verify, disable/enable the configuration, change model and bounded
daily/concurrency settings through authenticated, CSRF-protected APIs.
**B1 is metadata/secret management only. available_to_users is permanently false.**
Stored daily and concurrency values are NOT YET enforced as fleet budget guards.
Platform-funded Chat routing, paid model use, and full Chat redesign are NOT implemented.
No real DeepSeek key or paid request was used.

## Git ancestry and runtime isolation

- New branch: codex/p0-platform-providers-registry-001.
- Exact source parent: PR #279, 7270d9d2caf86dc6917497b6e2a07a3859d4af48.
- Previous main: 321fcb4fe193993db70aa705a46842e9836daac0.
- PR #279 remains open; this is a stacked change, NOT a merge to main.
- Stable D2-R2 demo: localhost:18080, Compose izo-asa-demo279, kept unchanged.
- B1 isolated preview: localhost:18081, Compose izo-asa-p0-preview.
- Separate Postgres/object volumes and explicit per-project network subnets.
- No changes to global Docker networking, Firewall, DNS, VPN, routes or other projects.
- Only a synthetic isolated P0 QA operator was bootstrapped. NOT the owner's account.

## Source reuse and ownership

| Existing target owner | Reused component | B1 change |
|---|---|---|
| Accounts | staff_session, password, CSRF, origin | Fresh staff/permission checks and reauthentication |
| Access | permissions registry/bootstrap | Existing connections.read/write and secrets.bind, no new roles |
| Chat credentials | AES-GCM and root key | Separate platform AAD/UUID namespace, no user-owned key |
| DeepSeek | existing adapter plus built-in fake | Real verification only by explicit action, fake only in test |
| Admin | append-only events | Metadata-only audit, no secret payload |
| Chat / Graph | existing conversations | Not modified; no second inference/request backend |
| Web | existing same-origin apiRequest and Admin navigation | New /admin/providers page with CSRF |
| PostgreSQL | Alembic migration | 0021_platform_chat_registry, new constrained table |

Fresh donor code was not imported; existing repository owners were reused.
Provider compatibility and actual paid results are NOT proven by synthetic tests.

## Security checks

- Read requires connections.read. Save/verify require connections.write and secrets.bind.
- Settings require connections.write. Fresh password proof and recheck before write.
- Secret is write-only AES-GCM ciphertext, never present in GET/DTO or audit.
- Rotation invalidates verified status and disables the connection.
- Mere save does not set verified. Synthetic verification uses FakeDeepSeekProvider.
- UUID replay, stale revision and conflicting intents are rejected.
- Models bounded to deepseek-flash and deepseek-v4-pro, no arbitrary provider URL.
- Daily bounds 1–200, concurrency 1–10; not yet charged/spend-limited.
- A normal registered account is denied staff operations.

## Tests and screenshots

- P0 focused Linux pytest: 14 passed, 0 failed (isolated --network none).
- Compose build / TypeScript typecheck / API readiness / migration completed.
- Chromium browser: 13 actual checks PASS including save, verify, model/policy,
  disable/reenable, reload, route visibility, mobile 390px without page overflow.
- Initial UI omitted CSRF token; observed POST 403. Corrected and retested HTTP 200.
- Restarted P0 containers; API/Web/Postgres healthy; migration version 0021.
- Actual DeepSeek response: NOT TESTED. Staff catalog/grants mutations: NOT TESTED.

| Real browser screenshot | Evidence |
|---|---|
| Before Admin connection | Desktop before: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_B1_before_desktop.png` |
| After saving and verifying | Desktop after: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_B1_after_desktop.png` |
| Responsive layout | Mobile after: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_B1_after_mobile.png` |

## Unresolved acceptance and next dependencies

1. Independent security and read-only source review: PENDING; this is NOT an approval.
2. Exact-head full required GitHub CI: PENDING until PR creation.
3. Confirm real owner's identity before a real staff bootstrap.
4. P0-B2/C needs account admission, charged-request routing, global concurrency,
   daily spend enforcement, replay/recovery and zero-BYOK browser E2E.
5. P0-D must improve overall desktop/mobile UI. Existing narrow mobile topbar is cramped.
6. Do not merge this stacked draft PR or modify protected main without owner decision.

## Follow-up: recovery, session invalidation and concurrent singleton (24 October 2026)

- Previous exact source `7eccd15605f2d8cc8e5e9d66370d34f1548db9ed` received three independent P1 findings concerning an uncertain mutation's failed GET, session invalidation, and missing real PostgreSQL singleton acceptance.
- A failed operator reconciliation GET now leaves the original volatile operation UUID/payload and the mutation lock intact. A successful GET is required before any explicit abandonment releases the pending operation. Exact-repeat uses the original ID and body.
- The shared `izo:session-invalid` event clears the private key, current password, pending operation and provider snapshot, unmounts mutation controls and ignores late GET responses. Private data does not enter persistent browser storage.
- Isolated D2-R2 Chromium regression: 4/4 PASS (phone + laptop, no retries), demonstrating the failed read plus exact-ID replay and session invalidation. TypeScript and production Vite: PASS.
- A separate isolated PostgreSQL 17 container, with network isolation and two verified authorized staff accounts, exercised **actual** `PlatformProviderService.replace_key` concurrently. The calls were aligned after per-account authorization and before the singleton lock: exactly one revision-1 creation, one HTTP-semantic 409 revision conflict, a single success event, and replay of the exact winning operation without an additional success event. Output `P0_280_REAL_PG_SINGLETON_CONCURRENCY_PASS`; confirmed synthetic operations only; container/network removed. QA script: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_280_CONCURRENT_INIT_20261024.py` (untracked, no production credentials).
- Real-PostgreSQL **CI wiring** remains an explicit review gate and should be combined with the already-approved `tools/platform_chat_postgres_race.py` in downstream PR #281, avoiding unauthorized changes to #280's 24/26 source scope. Local isolated QA is not represented as GitHub CI.
- These changes do not authorize merge, paid-provider tests or production deployment. New exact-SHA CI and independent review are mandatory.

## Follow-up: HTTP 429 uncertainty and verify replay race (24 October 2026)

- Starting source: `c2a57a81ebe74073463af076919f51429b9017c8`. These corrections remain limited to PR #280; no main merge or owner waiver.
- P1: a throttled HTTP 429 **on a replay of an already uncertain operation** preserves the exact original in-memory UUID and payload, along with the disabled mutation controls. A first-attempt definitive 429 is still handled normally. Successful authoritative replay or successful GET reconciliation is required to unlock. The `izo:session-invalid` cleanup remains intact.
- P2: the final `PlatformProviderService.verify` transaction rechecks the exact UUID and fingerprint under the provider row lock **before** rejecting changed revision/generation; an exact already-committed replay returns its receipt without a duplicate successful audit event. A mismatched fingerprint remains `409 idempotency_conflict`; a different operation racing with credential rotation remains `409 provider_changed_during_verify`.
- Regression-first proof: before the P2 fix, the deterministic overlapping real HTTP verify test failed with `409 provider_changed_during_verify`. After the fix the complete isolated `tests/test_platform_providers_http.py` passed **15/15**, including nested overlapping HTTP verification, receipt equivalence, a single success audit event and wrong-fingerprint rejection.
- Real Chromium on D2-R2, new isolated compiled frontend `127.0.0.1:18121`, synthetic API interception: **4/4 PASS** at 390px/1440px, with lost response → same UUID retry → HTTP 429 → retained pending/disabled writes → failed reconciliation GET → exact UUID success, plus session-invalid zero-private-controls cases. No live provider calls or production data. QA evidence: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_280_REPLAY_20261024.json`.
- TypeScript and production Vite build PASS. `check_docs.py`, `repository_hygiene.py` against stacked base `7270d9d...` and `git diff --check` PASS. The HTTP test was factored within its existing permitted file to remain below the original handwritten size/line warning threshold; no gate, retry, timeout, scope `max_files` or source allowlist was raised.
- `project_state.py verify` on the standalone #280 development worktree reports the existing mismatch between its local worktree branch and the canonical active package `P1-CHAT-THREAD-SEARCH-001`; no state files were modified. Required exact-source GitHub CI and independent security review remain pending until publication of the new source SHA.
