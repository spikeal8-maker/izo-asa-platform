# CHAT-DEEPSEEK-001 · D1 implementation contract

## Before → after
Before: the accepted Chat shell stores only in-memory user turns and explicitly has no text backend.
After: an authenticated preview account can store its write-only DeepSeek key, select a server allowlisted text model, create a durable thread/request, receive an actual streamed assistant response, ask a contextual follow-up, reload the thread from PostgreSQL, and issue a server Stop.

## Fixed implementation decisions
- Package/base: `CHAT-DEEPSEEK-001` from `maint/state-decision-003@1120121c0fd1f6d9279aa3e95523bb48d5b906f8`.
- Execution owner: FastAPI `api` service. D1 uses bounded request-scoped provider execution; no new broker or image Jobs reuse.
- Provider origin: fixed `https://api.deepseek.com`. Browser never receives or selects an upstream URL/header.
- Text allowlist revision `deepseek-2026-09-d1`: `deepseek-flash`, `deepseek-v4-pro`; preview default `deepseek-flash`.
- Root key: `IZO_CHAT_ROOT_KEY`, 32 random bytes encoded URL-safe base64, generated once into local runtime `.env`; never PostgreSQL, image, Git, ZIP or browser. Only the API service receives it.
- Credential encryption: AES-256-GCM from `cryptography`; AAD binds account, connection and generation. DB stores ciphertext/nonce and metadata only.
- Preview admission: `IZO_CHAT_PREVIEW_ACCOUNT_EMAILS`; the first user registers through the normal UI with an allowlisted email. No manual SQL/staff grant is required.
- Test transport: deterministic fake provider is permitted only with `IZO_ENVIRONMENT=test`; development preview uses the real DeepSeek transport.

## Numeric D1 limits
- user input: 6,000 Unicode characters;
- context: at most 40 completed messages and 24,000 characters before the current turn;
- output request cap: 2,048 tokens;
- provider/request deadline: 75 seconds;
- one active request per thread;
- request admission: 20 starts per account per rolling 5-minute DB window;
- credential mutations/verification: 6 per account per rolling 5-minute DB window;
- thread list page: 50; message page: 100;
- provider SSE line: 256 KiB maximum; accumulated assistant text: 64,000 characters.

## Failure semantics
- Same request UUID + same fingerprint reuses the durable request; different material conflicts. A DB uniqueness/lock boundary prevents a concurrent second execution.
- Accepted request pins model revision, connection id and credential generation. Key replacement never mutates an accepted snapshot.
- Final assistant text is persisted before terminal `done`. Partial text may be persisted and remains explicitly `interrupted`/error after failure; no automatic paid retry.
- Stop is an owner-only server state transition plus execution cancellation signal. It does not promise that the upstream provider has stopped billing after bytes already sent.
- Provider/auth/rate/timeout errors are normalized. Raw provider bodies, Authorization, plaintext/ciphertext keys and tracebacks are not public output.

## Non-goals
No redesign; no attachments, mic/ASR, image tools, web search, provider admin, ASA Lab, merge/deploy or paid live smoke.
