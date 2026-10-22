# P0-B2/C · No-BYOK synthetic platform Chat · exact implementation evidence

## Boundary and lineage

This package is **only** a no-spend, test-gated functional vertical.
Base SHA: `6ae8c91a3297d3ec754872aaa04766cc5ceb1538` (PR #280).
PR #280 stacks on unmerged PR #279. No merge to protected `main`.
Source branch: `codex/p0-platform-chat-fake-001`.

**This is not a paid-provider integration and not complete financial accounting.**
All external model calls are prohibited. In this slice the existing
`FakeDeepSeekProvider` returns labelled deterministic chunks, cost=0.
The admin daily number is a request cap, not a monetary budget.
Future paid execution requires authentic token usage/costs, reservation,
currency handling, limits, reconciliation, timeout/failover/lease controls
and separate owner approval.

## Actual behavior

- Existing Accounts session + Chat preview email allowlist gate admission.
- Existing Chat runtime/Graph/SSE persists user messages, attempts, branches
  and full streamed response; no second Chat backend.
- An account without a personal DeepSeek or OpenRouter credential can select
  `platform:deepseek-flash` if the admin connection is configured and verified.
- Synthetic platform responses have the visible "test" marker.
- Existing BYOK remains available as an independent option.
- New mode requires **both** `IZO_ENVIRONMENT=test` and
  `IZO_CHAT_PLATFORM_DEMO=isolated` in the API process.
  Default/real deployments cannot select the fake platform model.
- Account-owned shadow connection records are encrypted references only.
  They hold a fixed dummy credential, **not** the platform's actual key.
  The existing execution path obtains the central secret in the API only
  after verifying account ownership, provider state and generation.
- Admission locks one PostgreSQL platform connection row, then checks
  global in-flight requests and UTC daily usage, then atomically persists
  usage + shadow binding + Graph request in the same database transaction.
  A failed admission rolls back every increment.
- The existing UUID replay is checked before a new admission; changed
  intent returns conflict. UNKNOWN_PAID_OUTCOME blocks a second submission.
- Provider disabled or rotated: no new platform requests; old completed
  conversations remain readable and stale pending credentials fail closed.
- For this isolated fake, persisted `confirmed_cost_microusd` is zero.
  **No paid cost estimation or charging is claimed.**

## Tests executed on D2-R2

| Evidence | Observation |
|---|---|
| Network-disabled SQLite domain/HTTP tests | Platform/no-key/BYOK, replay, daily/concurrent limits, unknown outcome, rotation and tenancy |
| Real PostgreSQL parallel HTTP requests | Two separate accounts => one 202 and one 429 when concurrency=1 |
| Exact UUID replay | HTTP 202 for same request ID, no second daily charge |
| SSE terminal | `event: message.done`, persisted request state `completed` |
| Daily quota | final slot succeeds; next 429 and count unchanged |
| Disabled provider | Model disappears; new admission rejected |
| PostgreSQL absent-row race | Six simultaneous transactions: 3 admitted, 3 rejected; count=3, cost=0 |
| Playwright mock-contract UI | 4/4 PASS on laptop and 390px phone |
| Real D2-R2 Chrome | Registration, no user BYOK, fake SSE, full history and mobile overflow PASS |
| Admin refresh | Test-only throttling exercised; normal admin API restored enabled state |
| Secret boundaries | Model/Graph/credentials APIs exclude key and ciphertext |

QA artifacts and BEFORE/AFTER screenshots live on D2-R2 under
`C:\Users\spike\Projects\izo-asa-p0-preview-qa`; no PNG assets
are tracked in Git to preserve repository hygiene.
The optional dedicated CI job runs real PostgreSQL absent-row races in an
isolated ephemeral Compose database and explicitly destroys only that
workflow's disposable volumes.

## Source ownership and tests

- API: `apps/api/izo/chat/platform_admission.py`,
  `platform_policy.py`, existing Graph/Execution/Catalog, and
  `apps/api/izo/platform_providers/`.
- Migration: `0022_platform_chat_fake_demo.py`, adds a reserved
  per-account platform-shadow provider identifier and UTC daily usage.
- Web: `ChatStartNotice.tsx`, `modelCatalog.ts`,
  `useChatPreflight.ts`, existing composer and message components.
- Default test suite: `tests/test_platform_chat_fake.py`.
- Real PG script: `tools/platform_chat_postgres_race.py`.
- Browser contract: `apps/web/e2e/platform-fake-chat.spec.ts`.
- CI: `.github/workflows/p0-platform-fake.yml`.

## Release/acceptance HOLD

1. Exact-HEAD full Foundation CI and dedicated PostgreSQL workflow must pass.
2. Independent reviewer must validate ownership, locking order, shadow
   lifecycle, spend-fail-closed boundary and UUID/outcome semantics.
   Implementer tests are not a substitute for independent APPROVED.
3. Requires unmerged PR #280 and PR #279; no protected-main merge or
   owner waiver without explicit owner decision.
4. Do **not** expose a paid platform endpoint, API key or network access.
5. Real DeepSeek, budget settlement, actual provider workers and deployment
   outside loopback remain NOT TESTED / NOT AUTHORIZED.
