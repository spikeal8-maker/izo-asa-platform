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
