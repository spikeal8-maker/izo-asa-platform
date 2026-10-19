# Chat owner

Chat owns account-scoped DeepSeek/OpenRouter credentials, durable conversation
state and `/api/v1/chat/*`. The API is the sole executor. The browser receives no
provider key, endpoint, ciphertext, database owner selector or paid retry authority.
PostgreSQL stores encrypted credentials; the AES-GCM root key comes from API
configuration, outside database backups and preview archives.
`IZO_ENVIRONMENT=test` may inject fake providers; development never silently does.

OpenRouter uses a fixed API origin and bounded catalog. External USD metadata and
Admin-owned RUB prices remain separate; missing prices stay unknown. Chat policy
lives in `schemas.py`; published DeepSeek policy lives in `../catalog/`.

Before provider POST, a request commits its unknown-outcome marker. Uncertain
response, disconnect or restart preserves it and blocks another execution in that
thread; exact request-ID replay remains safe. There is no in-app reconciliation
in this preview. The user must verify provider result/charge before retrying
elsewhere. The Compose preview uses one API worker; scaling needs a lease/fence.

Images reference owned ready shared Media assets. `attachments.py` admits ordered
normalized PNG snapshots; `vision.py` loads private bytes with an aggregate bound
before provider submission. Admission persists vision capability so execution and
replay do not depend on later catalog availability. Media owns upload policy,
S3 reconciliation and downloads.
DeepSeek Flash vision is an explicit Chat adapter capability in `catalog.py`,
following the [DeepSeek vision API](https://api-docs.deepseek.com/guides/vision/).
OpenRouter vision uses catalog `input_modalities`; Admin `text` controls prices.

## Conversation graph

`graph_tables.py` owns immutable turns/attempts, branch membership, per-branch
selection and private context evidence. `chat_thread_graphs` owns active branch
and revision. Forward migrations `0018`/`0019` retain original IDs, messages,
attachments, manual titles and recorded context bytes. Unrecorded legacy context
stays explicit; only an actual pending claim captures `legacy_claim` evidence.

`ThreadDetail.graph_version = 1` advertises Graph. `history_pages.py` returns
50 turns (`GET .../graph?before_turn_sequence=N`) or 20 visible attempts
(`GET .../turns/{turn}/attempts?before_ordinal=N`). Optional `branch_id` fences
both reads. Cursors are exclusive; count, position and neighbors use membership.
`branches.py` lists 50 branches with exclusive `before_branch_ordinal`, plus the
active branch even outside the page. `PATCH .../branch-selection` uses observed
branch/revision and returns a coherent Graph page. History is unchanged.

`graph_requests.py` admits send, `POST .../turns/{turn}/regenerate` and
`POST .../turns/{turn}/edit` through one execution path. Edit atomically creates a
child, inherited prefix membership/selection and a new user/request. Source and
suffix remain intact; later parent/sibling versions never enter the child.
Source model and ordered assets are revalidated. Text keeps raw 6000-code-point
bounds and Python strip; unchanged text rejects before expiry, rate or admission. Ordinary `/requests` accepts an all-or-none
branch/revision pair; new unfenced sends on branched threads fail closed.

Exact UUID replay precedes fresh validation without readmission or reactivation.
Edit returns its immutable created branch and current active branch/revision.
Regeneration returns its recorded `execution_branch_id` and that branch's turn
projection separately from actual active branch/revision. Changed intent conflicts.
`PATCH .../turns/{turn}/selection` selects visible completed versions within the
active branch; completion only promotes inside its execution branch. Failure and
late lifecycle writes cannot replace completed content. Pending/streaming blocks
Edit and branch switching. UNKNOWN blocks execution across the entire thread but
permits metadata switching; every Graph page retains the thread-wide warning.

Owned Thread → Request locks serialize mutation and coherent projections under
PostgreSQL READ COMMITTED. `graph_context.py` freezes the selected membership
prefix and current user at admission, excluding alternatives and later suffix.
Integrity is verified before the paid marker; DTOs and decisions live in
`docs/ARCHITECTURE.md` §10 and the Edit review.

## History and titles

Existing detail returns the latest 100 physical messages and `next_before_sequence`;
`GET /threads/{id}/messages?before_sequence=N` pages older physical messages with an
exclusive monotonic sequence cursor. Graph does not reinterpret this contract.
`thread_pages.py` returns 50 owned threads by exclusive `(created_at, id)` cursor.
Ownership is checked before messages/attachments; cursors confer no permission.

`PATCH /threads/{id}` uses existing session, origin and CSRF checks. `ThreadRename`
trims browser Unicode whitespace and accepts 1–120 code points; NUL, lone surrogates
and whitespace-only input fail safely. `thread_titles.py` locks the same owned thread
as first admission and persists private `title_is_manual`, including manual
`Новый чат`. Rename preserves creation order, messages, requests and cursors.

## Sources and nearest tests

Behavior owners: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/AI_RUNTIME.md`.
Process/source owners: `docs/MAINTAINABILITY.md`, `docs/DEVELOPMENT.md`.
Tests: `tests/test_chat.py`, `test_chat_multi_provider.py`, `test_chat_vision.py`,
`test_chat_vision_http.py`, `test_chat_history_paging.py`, `test_chat_thread_paging.py`,
`test_chat_thread_rename.py`, `test_chat_thread_rename_http.py`, and the four
`tests/test_chat_graph_{requests,context,http,migration}.py` and
`tests/test_chat_branches{,_http,_migration}.py`. Providers are synthetic.
