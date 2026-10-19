# Chat owner

Chat owns account-scoped DeepSeek/OpenRouter credentials, durable conversation
state and `/api/v1/chat/*`. The API is the sole executor. The browser receives no
provider key, endpoint, ciphertext, database owner selector or paid retry authority.
PostgreSQL stores encrypted credentials; the AES-GCM root key comes only from API
runtime configuration and is absent from database backups and preview archives.
`IZO_ENVIRONMENT=test` may inject fake providers; development never silently does.

OpenRouter uses a fixed API origin and bounded cached text-model catalog. External
USD metadata is separate from Admin-owned informational RUB prices. Missing prices
remain unknown, without implying free use or a platform debit. Chat policy bounds
live in `schemas.py`; published DeepSeek policy lives in `../catalog/`.

Before provider POST, a request commits its unknown-outcome marker. Uncertain
response, disconnect or restart preserves it and blocks another execution in that
thread; exact request-ID replay remains safe. There is no in-app reconciliation
in this preview. The user must verify provider result/charge before retrying
elsewhere. The Compose preview uses one API worker; scaling needs a lease/fence.

Images reference owned ready shared Media assets. `attachments.py` admits ordered
normalized PNG snapshots; `vision.py` loads private bytes with an aggregate bound
before provider submission. Admission persists vision capability so execution and
replay do not depend on later catalog availability. Media owns upload policy,
S3 reconciliation and downloads; Chat adds no image generation path here.
DeepSeek Flash vision is an explicit Chat adapter capability in `catalog.py`,
following the [DeepSeek vision API](https://api-docs.deepseek.com/guides/vision/).
The Admin `text` modality controls publication/prices, not image capability.
OpenRouter vision comes from current catalog `input_modalities`.

## Conversation graph

`graph_tables.py` registers root Branch, immutable Turn, one Attempt per ChatRequest,
selected attempts and private context evidence. `chat_thread_graphs` owns active
branch and monotonic revision; Attempt lifecycle derives from ChatRequest, including
credential disable and restart. Forward `0018` retains original IDs, messages,
physical sequences, attachments and manual titles. Historical contexts remain
`legacy_unrecorded`; actual pending claim captures honest `legacy_claim` evidence.

`ThreadDetail.graph_version = 1` advertises the additive Graph API. `history_pages.py`
returns at most 50 turns through `GET /threads/{id}/graph?before_turn_sequence=N`.
`GET /threads/{id}/turns/{turn}/attempts?before_ordinal=N` returns at most 20 attempts
and fresh selected-turn metadata, including selected versions outside that page.
Both cursors are exclusive. Completed count, position and neighbor IDs allow bounded
version navigation. Display anchors stay stable when new physical messages append.

`graph_requests.py` owns send and `POST .../turns/{turn}/regenerate` admission.
Regeneration reuses the original immutable user and selected source's public model
identity, with fresh authorization, capability, rate and credential-generation checks.
Exact request-ID replay preserves its attempt without readmission; changed intent
conflicts. `PATCH .../turns/{turn}/selection` requires a fresh branch/revision and a
completed attempt. Only durable completed content atomically promotes a new attempt;
failure keeps selection. Manual selection and completion follow commit order.

`graph_selection.py` centralizes Thread → Request locks for admission, claim, paid
marker, partial, stop and completion. Owned-thread projection reads keep revision
and selection coherent under PostgreSQL READ COMMITTED. Late partial/final calls
cannot rewrite completed content or promote it again. `graph_context.py` freezes
selected complete prefix groups and the original current user at admission, with
policy, message/attachment identities and digests. Earlier-turn regeneration excludes
alternatives and later suffix. Integrity and owned bytes are checked before the paid
marker. Russian reply preference is versioned in that snapshot. Branch editing and
the general Context Engine remain future work; details are in `docs/ARCHITECTURE.md` §10.

## History and titles

Existing detail returns the latest 100 physical messages and `next_before_sequence`;
`GET /threads/{id}/messages?before_sequence=N` pages older physical messages with an
exclusive monotonic sequence cursor. Graph does not reinterpret this contract.
Thread-list `thread_pages.py` returns at most 50 owned rows in creation order using
exclusive immutable `(created_at, id)` cursor. Every read verifies ownership before
messages/attachments; cursors confer no permission.

`PATCH /threads/{id}` uses existing session, origin and CSRF checks. `ThreadRename`
trims browser Unicode whitespace and accepts 1–120 code points; NUL, lone surrogates
and whitespace-only input fail safely. `thread_titles.py` locks the same owned thread
as first admission and persists private `title_is_manual`. Manual `Новый чат` is
protected; create semantics stay compatible. Repeated rename is a no-op and never
changes creation order, message sequence, requests or cursors.

## Sources and nearest tests

Behavior owners: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/AI_RUNTIME.md`.
Process/source owners: `docs/MAINTAINABILITY.md`, `docs/DEVELOPMENT.md`.
Tests: `tests/test_chat.py`, `test_chat_multi_provider.py`, `test_chat_vision.py`,
`test_chat_vision_http.py`, `test_chat_history_paging.py`, `test_chat_thread_paging.py`,
`test_chat_thread_rename.py`, `test_chat_thread_rename_http.py`, and the four
`tests/test_chat_graph_{requests,context,http,migration}.py` files. Providers are synthetic.
