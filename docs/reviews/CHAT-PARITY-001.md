# CHAT-PARITY-001 · implementation contract

## Before → after

Before: the local preview on port 18080 has the Admin entry and revised shell, but Chat admits only DeepSeek text. It presents a file control whose selected file cannot be sent. The OpenRouter credential and model selection available in the separate port 5190 development checkout are absent. Chat has no server-owned preference for the response language and its reading column expands excessively on wide screens.

After: the canonical preview supports server-owned OpenRouter BYOK credentials, a bounded model catalog and real text streaming alongside DeepSeek. The UI exposes provider settings and model choice, shows unknown RUB prices honestly, removes unsupported file/tool actions until their backend exists, and restores a bounded reading column. The server asks providers to answer in the user's language, defaulting to Russian for this Russian-language preview.

## Package, scope and risk

- Package `CHAT-PARITY-001`, branch `codex/chat-parity-001`, base `e7af398cfc731027ab2a526451f52ac98509cdbe`.
- Finite cross-domain scope: at most 40 files, listed in `tools/scopes/chat-parity-001.json`. OpenRouter text is one end-to-end slice. Incoming images and vision require a subsequent package because the machine scope limit is hard.
- Non-goals: image generation, image upload or vision, Credits debits, payments, RUB conversion from provider USD rates, real provider calls, copying old encrypted credentials/database, modifying the old checkout, merge or public release.
- Risk: high for encrypted credentials, migration, provider admission and paid external execution. Browser cannot own provider keys or request retries. OpenRouter unknown outcomes quarantine the same thread and are not automatically retried. This preview has no in-app reconciliation endpoint; the warning asks the user to check the provider's result/charge before considering any manual action elsewhere.
- Nearest acceptance: provider/credential HTTP and failure tests, migration upgrade, catalog admission and language wire tests, web provider settings/model picker E2E, responsive layout and existing Admin regressions; then complete CI and independent review or exact-SHA owner waiver.

## Evidence and self-review

The implementation now restores OpenRouter text BYOK, credential settings, server catalog admission, model search and a bounded Chat reading column. Unsupported file/tool actions are disabled. The server adds a Russian reply preference but model compliance is not guaranteed. Old and new Docker projects have separate databases/encryption roots; no credential was copied, and the user must enter their OpenRouter key in the new preview.

Provider risk review found and fixed a missing-price-as-zero bug, remote catalog fetch under a database lock, repeated failed catalog fetches, overflow parsing, a cross-account request-ID preflight distinction, and a blind resend path after uncertain OpenRouter POST. The final path records an unknown marker before POST, retains it across timeout/stop/disconnect/restart, blocks new UUIDs in the same thread, and exposes an explicit warning during streaming, stop and thread reload. The marker uses the existing request error field. A new thread can be created manually, so the UI warns that a provider charge may already exist. In-app reconciliation remains future work; the single-worker local preview is not a multiworker execution design.

Verification so far: isolated Linux profile: 57 focused tests passed, 1 PostgreSQL-gated case skipped; a populated PostgreSQL 17 migration smoke preserved the synthetic DeepSeek credential byte-for-byte and allowed an independent OpenRouter credential. Web build and focused provider E2E passed, including stop/reload warning. The broad local Python run passed product tests but three Git-dependent cases could not run inside the minimal container; those three and the machine-plan size case passed on the Windows host. Scope is 40/40, OpenAPI export/check and docs/state checks pass. Independent local security review: PASS with the same-thread quarantine limitation; this is not a GitHub APPROVED review. Full Playwright matrix, required GitHub CI and local Docker preview verification remain pending. Verdict: **FIX_REQUIRED** until those gates finish.
