# Platform provider registry · P0-B1 / isolated P0-B2 fake

One Accounts/Access-governed **server-owned** DeepSeek key: encrypted PostgreSQL
ciphertext under a platform-specific AES-GCM AAD and namespace. Never return
plaintext, nonce, ciphertext or owner selector in public responses.

P0-B1 staff endpoints reuse Accounts session, CSRF, same-origin, current-password
reauthentication, `connections.read`, `connections.write` and `secrets.bind`.
Rotation invalidates verification and disables the setting; audit records
nonsecret action metadata. Personal BYOK remains independent.

P0-B2/C synthetic acceptance is **explicitly opt-in**: both
`IZO_ENVIRONMENT=test` and `IZO_CHAT_PLATFORM_DEMO=isolated` must be
present in the server process. Only the normal Chat preview account allowlist
can use this path. Real provider execution is **not enabled** by this flag:
test environment creates only `FakeDeepSeekProvider`.

The existing Chat/Graph/Request API implements admission, SSE, persisted history,
branching, UUID replay and UNKNOWN_PAID_OUTCOME. On isolated demo, one global
PostgreSQL platform row lock serializes admission across accounts before reading
the daily usage row or inserting per-account **shadow references**.
The shadow credential holds an encrypted placeholder, not the shared provider key.
Chat execution rechecks platform state/generation and decrypts the central key
on the server only. A rotated or disabled provider cannot start a new request.

Daily admission and global concurrency are bounded by database transactions;
errors 429 are returned without increasing the durable daily counter.
The `confirmed_cost_microusd` column remains **exactly zero only because this
mode never calls a paid service**. This is not real paid-cost accounting.
True USD/RUB token reconciliation, budget reservation, spend caps, fleet leases
and live provider failover are explicitly **NOT IMPLEMENTED**.

Test entrypoints: `tests/test_platform_chat_fake.py`,
`apps/web/e2e/platform-fake-chat.spec.ts`,
`tools/platform_chat_postgres_race.py` and
`.github/workflows/p0-platform-fake.yml`.
Never use this package or synthetic assertions as approval for a paid deployment.
