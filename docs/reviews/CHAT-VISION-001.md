# CHAT-VISION-001 · implementation contract

## Before → after

Before: the canonical Chat preview on port 18080 has DeepSeek and OpenRouter text chat, but its attachment control is disabled, policy advertises zero attachments, messages have no private image references, and vision models cannot receive Media assets.

After: the Chat composer can accept PNG/JPEG/WebP by file selection, paste or drop, upload through the shared Media service, and send ordered attachment IDs. The backend admits only assets owned by the current account, persists message references, and constructs private vision input for a verified vision model. Saved chats render their own images after refresh and restart.

## Package, scope and risk

- Package `CHAT-VISION-001`, branch `codex/chat-vision-001`, base `67233e203436f56b77add709e04f01610ac462f3`, depends on `CHAT-PARITY-001`.
- Finite cross-domain scope: at most 40 paths in `tools/scopes/chat-vision-001.json`; the initial list contains 39 paths and leaves one path for a necessary acceptance adjustment. Backend and web files are disjoint for parallel implementation. The existing Account, Media and Chat services remain the owners of identity, objects and conversations.
- Non-goals: in-chat image generation, a second Media store or gallery, GIF support, Admin pricing, Credits debit, payments, real provider calls, importing the old database, merge and public release.
- Risk: high for private images, cross-account ownership, provider transmission, object validation, upload idempotency and uncertain paid outcomes. Media upload outcomes must be reconciled with the same operation/upload ID; paid Chat requests must preserve the existing unknown-outcome barrier. Browser input is never trusted for ownership, model capability, object key or price.
- Nearest acceptance: schema and migration tests, foreign/corrupt/duplicate/oversize asset negatives, ordered exact replay, Media→Chat HTTP tests on isolated PostgreSQL/S3, browser file/paste/drop/remove/render/reload/responsive tests, then full required CI and independent GitHub review or exact-SHA owner waiver.

## Donor analysis

The old `IZO_ASA` checkout provides a Media-backed attachment and vision starting point, but its migration `0013_chat_vision` conflicts with the canonical Admin migration. The new migration must be `0015_chat_vision` descending from `0014_chat_multi_provider`. Its browser accepts GIF while canonical Media does not; its five times 12 MiB allowance can exceed the 24 MiB vision context. The donor also creates fresh upload operations after unknown outcomes and imports an internal Gallery component into Chat. These defects must be corrected during the port, not copied.

## Evidence and self-review

Implementation and tests pending. No production keys or paid provider calls are authorized for this package. The previous text package passed all required CI for exact source SHA `67233e203436f56b77add709e04f01610ac462f3`; the sole owner authorized the exact-SHA waiver because no other participant is available. That waiver does not apply to this package.
