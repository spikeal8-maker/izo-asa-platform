# CHAT-VISION-001 · implementation contract

## Before → after

Before: the canonical Chat preview on port 18080 has DeepSeek and OpenRouter text chat, but its attachment control is disabled, policy advertises zero attachments, messages have no private image references, and vision models cannot receive Media assets.

After: the Chat composer can accept PNG/JPEG/WebP by file selection, paste or drop, upload through the shared Media service, and send ordered attachment IDs. The backend admits only assets owned by the current account, persists message references, and constructs private vision input for a verified vision model. Saved chats render their own images after refresh and restart.

## Package, scope and risk

- Package `CHAT-VISION-001`, branch `codex/chat-vision-001`, base `67233e203436f56b77add709e04f01610ac462f3`, depends on `CHAT-PARITY-001`.
- Finite cross-domain scope: at most 40 paths in `tools/scopes/chat-vision-001.json`; the list contains 40 paths, including mandatory CI wiring for the isolated Media→Chat restart acceptance. Backend and web files are disjoint for parallel implementation. The existing Account, Media and Chat services remain the owners of identity, objects and conversations.
- Non-goals: in-chat image generation, a second Media store or gallery, GIF support, Admin pricing, Credits debit, payments, real provider calls, importing the old database, merge and public release.
- Risk: high for private images, cross-account ownership, provider transmission, object validation, upload idempotency and uncertain paid outcomes. Media upload outcomes must be reconciled with the same operation/upload ID; paid Chat requests must preserve the existing unknown-outcome barrier. Browser input is never trusted for ownership, model capability, object key or price.
- Nearest acceptance: schema and migration tests, foreign/corrupt/duplicate/oversize asset negatives, ordered exact replay, Media→Chat HTTP tests on isolated PostgreSQL/S3, browser file/paste/drop/remove/render/reload/responsive tests, then full required CI and independent GitHub review or exact-SHA owner waiver.

## Donor analysis

The old `IZO_ASA` checkout provides a Media-backed attachment and vision starting point, but its migration `0013_chat_vision` conflicts with the canonical Admin migration. The new migration must be `0015_chat_vision` descending from `0014_chat_multi_provider`. Its browser accepts GIF while canonical Media does not; its five times 12 MiB allowance can exceed the 24 MiB vision context. The donor also creates fresh upload operations after unknown outcomes and imports an internal Gallery component into Chat. These defects must be corrected during the port, not copied.

## Evidence and self-review

Implementation covers private Media-backed image selection, ordered persistence,
vision payloads, and same-ID Media reconciliation. Server tests passed 57/57 in
Linux Docker. The isolated PostgreSQL/S3 HTTP acceptance passed before and
after a full container restart using the exact CI `docker compose exec`
invocation. Web build and focused browser cases passed. The first complete
local browser run recorded 704 pass, 207 skip, 20 failures in two existing
catalog tests across viewport projects; both failures were changed error copy,
which was corrected without altering those tests. The four affected phone and
laptop cases then passed. Required GitHub CI remains pending.

SELF_REVIEW: `PASS` for the finite image-attachment slice. Scope is 40/40 and
`check_change`, `check_docs`, `project_state verify`, and `git diff --check`
pass. The shared Account/Media/Chat ownership boundary, asset integrity,
idempotent upload operation and paid-outcome barrier remain server-side. No
test or size limit was weakened. New handwritten files remain below the 80%
warning threshold; existing Composer/runtime files approach it and should be
split before their next substantial feature.

Residual risk: an uncertain Chat admission ID is held only in the current tab's
memory. New/Open Chat in that tab preserve the draft and ID, but a closed or
reloaded tab cannot safely infer whether the POST was accepted. Cross-tab Chat
admission recovery needs a separate privacy-aware design. Open product gaps are
in-chat image generation and visible/admin-configurable image prices in RUB.
Real provider calls, production keys and spend were not used. The prior
owner waiver applies only to SHA `67233e203436f56b77add709e04f01610ac462f3`;
this package still requires full CI and exact-SHA GitHub review or owner waiver.
