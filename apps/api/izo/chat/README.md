# Chat owner

Chat owns account-scoped DeepSeek/OpenRouter credentials, conversations
and `/api/v1/chat/*`; API alone executes. Browser receives no key, endpoint,
ciphertext, database owner selector or paid retry authority. Credentials are
encrypted in PostgreSQL; AES-GCM root key stays outside backups/previews in API
config. Fakes require `IZO_ENVIRONMENT=test`.

OpenRouter uses fixed origin/bounded catalog. External USD metadata and Admin RUB
prices stay separate; absent prices are unknown. Policy: `schemas.py`, `../catalog/`.
DeepSeek Flash vision is explicit in `catalog.py` per the
[vision API](https://api-docs.deepseek.com/guides/vision/); OpenRouter uses
`input_modalities`, Admin `text` controls prices.

Commit unknown-outcome marker before POST. Uncertain outcome/disconnect/restart
blocks another thread execution; exact-ID replay stays safe. No in-app reconciliation:
verify provider result/charge before retry. Single-worker preview needs
lease/fence before scaling. `attachments.py` admits ordered PNG snapshots of owned
ready Media; `vision.py` loads bounded private bytes. Persist vision capability at
admission for catalog-independent execution/replay. Media owns uploads/S3/downloads.

## Conversation graph

`graph_tables.py` owns immutable turns/attempts, branch membership/selection and
private context; `chat_thread_graphs` owns active branch/revision. Migrations
0018/0019 retain IDs, messages, attachments, manual titles and recorded context.
Missing legacy context stays explicit; actual pending claim alone records `legacy_claim`.

`ThreadDetail.graph_version=1` advertises Graph. `history_pages.py` pages 50 turns
(`GET .../graph?before_turn_sequence=N`) or 20 visible attempts
(`GET .../turns/{turn}/attempts?before_ordinal=N`); `branch_id` fences both.
Cursors are exclusive; counts/positions/neighbors use membership. `branches.py`
pages 50 branches by `before_branch_ordinal`, retaining the active branch outside
that page. `PATCH .../branch-selection` requires observed branch/revision and
returns coherent Graph; physical history is unchanged.

`graph_requests.py` admits send, `POST .../turns/{turn}/regenerate` and
`POST .../turns/{turn}/edit` through one path. Edit atomically creates child,
inherited prefix membership/selection and user/request; source/suffix and later
parent/sibling versions remain separate. Revalidate source model/ordered assets.
Text: raw 6000-code-point bound/Python strip; unchanged rejects before expiry/rate/
admission. `/requests` requires paired branch/revision; unfenced branched sends reject.

Exact UUID replay precedes validation without readmission/reactivation; changed
intent conflicts. Edit returns created branch and current branch/revision.
Regeneration returns recorded `execution_branch_id` and its projection separately
from current branch/revision. `PATCH .../turns/{turn}/selection` selects visible
completed versions in the active branch; completion promotes only within its
execution branch. Failure/late writes cannot replace completed content.
Pending/streaming blocks Edit/branch switching. UNKNOWN blocks thread-wide execution
but allows metadata switching; all Graph pages retain the warning.

Owned Thread → Request locks serialize mutation/coherent reads under PostgreSQL
READ COMMITTED. `graph_context.py` freezes selected prefix/current user at admission,
excluding alternatives/later suffix. Verify integrity before paid marker;
DTOs/decisions: `docs/ARCHITECTURE.md` §10.

## History and titles

Detail returns 100 latest physical messages and `next_before_sequence`;
`GET /threads/{id}/messages?before_sequence=N` pages older ones exclusively.
Graph leaves this contract intact. Check ownership before messages/assets.

`GET /threads` returns `ThreadList`: 50 owned threads, `created_at DESC, id DESC`,
exclusive cursor. `q` searches all owned titles in one SQL query (LIMIT 51).
Raw q: at most 256 code points (422 beyond); NUL/invalid Unicode: 400 `invalid_input`.
`thread_title_search_v1.py` trims JavaScript edge whitespace, then applies
whole-string Python 3.13/Unicode 15.1 lowercase to query
and complete title; match literal substring. No casefold/accent folding, NFC/NFKC, wildcards or JS Unicode parity. Empty normalized q retains ordinary list/v1 cursor. Normalized
q over 240 cannot match; still validate cursor. PostgreSQL `strpos`/SQLite `instr`
treat %, _ and backslash literally.

Search cursor v2 binds Account, normalized q, matcher version and created/id
boundary. Malformed/foreign/changed-query/version/mixed list-search cursors return
400 `invalid_thread_cursor`; cursors never grant ownership. Live pagination has
no duplicate IDs; creates above the boundary need refresh and rename can change
later membership. It is not a snapshot. Private `title_search_key` is backfilled
and atomically updated on create, first-admission auto-title and rename; no public
DTO field. Matcher/Unicode changes require explicit backfill/cursor version handling.

Nonempty searches share two nonblocking permits per API process before checkout;
release in finally on every path. Ordinary list bypasses it. After auth and
cursor validation, PostgreSQL search SELECT uses local `statement_timeout=1000ms`.
Permit refusal, pool TimeoutError, SQLSTATE 57014/55P03 return 503
`search_unavailable` after rollback, without partial pages, SQL disclosure or retry.
Preserve other errors, engine/auth semantics. No fleet rate limit or total HTTP deadline is promised.

`PATCH /threads/{id}` retains session/origin/CSRF. `ThreadRename` trims browser
whitespace, accepts 1–120 code points; NUL, lone surrogates and blank input reject.
`thread_titles.py` locks the same owned thread as first admission. Private
`title_is_manual` includes manual «Новый чат»; order/messages/requests/cursors stay intact.

## Sources and tests

Owners: `docs/{PRODUCT,ARCHITECTURE,AI_RUNTIME,MAINTAINABILITY,DEVELOPMENT}.md`.
Synthetic-provider boundaries: `tests/test_chat*.py`.
