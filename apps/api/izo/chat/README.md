# Chat owner

Chat owns account-scoped DeepSeek and OpenRouter credentials, durable text
Thread/Message/Request, provider-neutral streaming lifecycle and the
`/api/v1/chat/*` HTTP boundary. OpenRouter uses a fixed API origin and a
bounded, cached text-model catalog. Dynamic OpenRouter pricing is external USD
metadata; the Admin catalog owns informational RUB display prices. Missing
RUB prices remain unknown, never free or an implied platform debit.

The API service is the sole executor. The browser never receives a provider key, provider URL,
ciphertext, database owner selector or paid retry authority. PostgreSQL stores encrypted
credential material and chat state; the AES-GCM root key is supplied only through the API
runtime environment and is intentionally absent from database backups and preview archives.

`IZO_ENVIRONMENT=test` may inject `FakeDeepSeekProvider`; development never silently falls
back to it. A failed/unknown real execution is persisted as a non-success terminal state and
is not automatically submitted again.

Before any provider POST, the request receives a durable unknown-outcome marker.
An uncertain response, disconnect or executor restart preserves it; another
request in that thread is rejected while exact request-ID replay remains safe.
The preview has no in-app reconciliation yet. The user must check the provider
result/charge before manually trying anything elsewhere. The current Compose
preview uses one API worker; a multiworker runtime needs a lease/fence before
scaling this execution path.

Chat bounds live in `schemas.py`; published DeepSeek policy and informational
RUB display prices live in `../catalog/`. UI consumes server policy and catalog
endpoints. The provider key is never sent to the browser after submission.
The server adds a Russian reply preference while respecting an explicit user
language request.

Chat image references point only to account-owned ready assets from shared Media.
`attachments.py` admits ordered normalized PNG snapshots; `vision.py` loads
private bytes with an aggregate context bound before provider submission.
The request stores vision capability at admission so execution and replay do
not depend on a later remote catalog refresh. Media owns upload policy, S3
reconciliation and downloads. Chat has no image generation path yet.
DeepSeek Flash vision is an explicit Chat adapter capability in `catalog.py`,
based on the [DeepSeek vision API](https://api-docs.deepseek.com/guides/vision/):
Chat Completions accepts `image_url` parts with private base64 PNG data.
The Admin catalog's `text` modality controls publication and RUB text prices;
it does not grant image capability. OpenRouter vision comes from its fresh
model catalog's `input_modalities` and is captured on request admission.

## Canonical contracts and nearest tests

Current Chat implementation remains the owner described above. Future convergence reads product behavior from `docs/PRODUCT.md`, conversation/data boundaries from `docs/ARCHITECTURE.md`, provider/runtime rules from `docs/AI_RUNTIME.md`, and process/source rules from `docs/MAINTAINABILITY.md` + `docs/DEVELOPMENT.md`. Proposal snapshots are provenance, not default live authority.

Nearest current tests: `tests/test_chat.py`, `tests/test_chat_vision.py`, `tests/test_chat_vision_http.py` plus provider-specific Chat tests. P1 must converge these owners rather than invent a second Chat backend.

History reads use `history_pages.py`: thread detail returns the latest 100 messages and
`next_before_sequence`; `GET /threads/{id}/messages?before_sequence=N` returns
the next older bounded page. The cursor is exclusive over the thread's unique
monotonic sequence. Both reads verify account ownership before loading messages
or attachments. Nearest paging tests are `tests/test_chat_history_paging.py`.

Thread-list reads in `thread_pages.py` return at most 50 account-owned rows in creation order.
`next_cursor` is an exclusive immutable `(created_at, id)` keyset boundary for
`GET /threads?cursor=...`; malformed cursors fail closed. The cursor grants no
ownership and every page applies the account filter. Nearest tests:
`tests/test_chat_thread_paging.py`.

`PATCH /threads/{id}` renames an existing owned thread through the same session,
origin and CSRF boundary. `ThreadRename` accepts only a title, trims the browser's
Unicode whitespace set, and requires 1–120 Unicode code points; NUL, lone
surrogates and whitespace-only titles are rejected without echoing input.
`thread_titles.py` locks the owned thread row used by first-message admission
and atomically persists title, a private `title_is_manual` flag and update time.
Manual `Новый чат` is protected like any other chosen title. Existing create
semantics are preserved; only the explicit rename command marks a title manual.
Repeated identical renames are no-ops. Rename never changes creation order,
message sequence, requests or pagination cursors. The forward migration retains
existing titles with a false marker. Nearest tests:
`tests/test_chat_thread_rename.py`, `tests/test_chat_thread_rename_http.py`.

## Conversation graph and regenerated answers

`graph_tables.py` registers a root Branch, immutable Turn identities, one Attempt
per existing ChatRequest, persisted selected attempts and private context evidence.
`chat_thread_graphs` owns the active branch and a monotonic selection/layout revision.
Attempt lifecycle is derived from ChatRequest, including credential disable and
restart recovery; there is no second mutable execution state. Migration `0018`
preserves original message/request IDs, physical sequences, attachments and manual
titles. Existing executions retain honest `legacy_unrecorded` context provenance;
only a real future claim of a legacy pending request records `legacy_claim`.

`ThreadDetail.graph_version = 1` advertises the additive projection. Existing
physical history and its `before_sequence` cursor retain their original meaning.
`GET /threads/{id}/graph?before_turn_sequence=N` returns at most 50 immutable turns.
A regenerated assistant may have a later physical sequence while occupying the
same `assistant_display_sequence`. `GET /threads/{id}/turns/{turn}/attempts`
uses exclusive `before_ordinal` pagination with at most 20 attempts, plus fresh
selected-turn metadata even when the selected attempt lies outside that page.
Completed count, selected position and previous/next completed IDs support bounded
version navigation. The graph page also exposes the thread's active attempt and
terminal unknown-outcome request without treating a live paid marker as terminal.

`graph_requests.py` admits original sends and `POST .../turns/{turn}/regenerate`.
Regeneration uses the selected source attempt's public model identity, rechecks
current publication, capability, rate and credential generation, and appends one
request/attempt/assistant message for the original immutable user message. An exact
request-ID replay returns the existing attempt without re-admission; another
intent conflicts. Existing UNKNOWN barriers remain authoritative for new work.

`PATCH .../turns/{turn}/selection` accepts only completed attempts with the current
branch and revision. Admission leaves the old selection visible. Durable completed
content and automatic selection commit atomically; other terminal states never
promote an attempt. Manual selection and completion follow transaction commit
order, and a stale manual command conflicts. `graph_selection.py` centralizes the
Thread → Request lock order used by admission, claim, paid marker, partial write,
stop and completion. Graph reads lock the owned thread so revision and selected
mapping remain coherent under PostgreSQL READ COMMITTED. Late partial/final calls
cannot rewrite a terminal completed message or promote it again.

`graph_context.py` freezes the selected completed prefix at admission using whole
turn groups and existing bounded context policy. Earlier-turn regeneration excludes
its own older attempts and the later conversation suffix. Saved message/attachment
identities and content digests prevent a later selection or catalog refresh from
changing admitted execution. Owned attachment bytes and integrity are checked
before the durable paid marker. Context evidence, credential binding and provider
details remain private. Editing, branch switching and a general Context Engine
remain separate packages.

Nearest graph tests: `tests/test_chat_graph_requests.py`,
`tests/test_chat_graph_context.py`, `tests/test_chat_graph_http.py`,
`tests/test_chat_graph_migration.py`; all provider fixtures are synthetic.
