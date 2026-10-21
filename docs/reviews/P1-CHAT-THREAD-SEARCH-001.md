# P1-CHAT-THREAD-SEARCH-001 — implementation and review evidence

## Goal and accepted base

The owner selected server-side title search across the complete Account history, including threads beyond the first two 50-row pages. Reuse the existing Chat API, sidebar and persisted Conversation Graph. No second history surface, Chat execution backend or authentication owner is introduced.

Accepted predecessor: PR #277, source `d7727ac26346598ebf64d145fcbdd5b7f4581235`, ordinary merge `321fcb4fe193993db70aa705a46842e9836daac0`, tree `0b9c5344e017f7b76a419b491d24068f556e61cd`. The pre-merge exact-head owner waiver is comment 6309003038. The actual merge has its own push Foundation CI 39551265110 and Dependency Security 39551265154; their final successful conclusions must precede native activation.

The unchanged native `project_state.py begin-decided-next`, through the authorized GitHub Connector, activated this package from the accepted actual main. Its activation receipt SHA256 is `605cfce55b014f8bb73653d936d7d5504b4132b86afe07c4412c4faea6c26916`. Native postchecks confirmed the new branch/package, unchanged existing package records, byte-identical CHECKPOINTS and only the expected three canonical state deltas. The controller did not edit canonical state manually.

The Message Edit package remains terminal `complete`; all 30 prior checkpoints are preserved. The search package stays `active` during implementation and publication. Its future merge, waiver and closeout require separate owner acceptance.

## SOURCE_AUDIT — FULL, bounded to title search

The target source is the exact accepted merge above. Reuse the existing prepared audit and implementation contracts; inspect only the affected owners and their delta. Canonical owners are `docs/UX.md` Chat history, `docs/ARCHITECTURE.md` Chat, and the API/Web Chat READMEs. Existing target code owns the authenticated 50-row thread list, exclusive created-time/ID cursor, atomic rename and Graph open path. Local-only sidebar filtering is the capability gap. Existing Account, history, rename, Graph, Message Edit and browser tests remain authoritative regressions.

Applicable donor `spikeal8-maker/IZO_ASA` was freshly read at unchanged main `51543df2b6a559d693e3ed75b11baeacdb9033d3`; the prepared audit at that exact source is reused:

| Donor source | Classification | Decision |
| --- | --- | --- |
| `frontend/src/desktopChat/DesktopChatWorkspace.tsx` | ADOPT_BEHAVIOR | Retain trimmed, case-insensitive literal title matching as the user expectation; loaded-array filtering cannot satisfy full-history search. |
| `backend/app/services/phone_chat_history.py` | REJECT | Its updated-time LIMIT 50 history without search/cursors is weaker than the target created-time/ID pagination. |
| `backend/app/api/routers/phone_chat.py` and frontend Chat API | REJECT | No applicable full-history title-search contract; retain target API and auth. |
| `backend/test_phone_chat_history.py` | REJECT | No adequate search/isolation/pagination coverage; add target-owner tests. |

No donor code, schema, credentials, users, sessions, data or provider execution is imported. The owner-authorized prepared contract supplies the bounded decisions below. This is not a new broad platform audit or a claim that unimplemented behavior has passed.

## Bounded product and implementation decisions

The existing `GET /api/v1/chat/threads` gains optional `q`; it retains `ThreadList`, 50-row pages and ordinary list behavior when normalized `q` is empty. Search covers every owned title in SQL. Results use `created_at DESC, id DESC`, exclusive keyset boundaries and LIMIT 51. A page never duplicates an already traversed ID. This is live pagination: new rows above the boundary require refresh; rename can change membership of later pages.

Matcher v1 trims explicit JavaScript edge whitespace and applies whole-string Python 3.13 / Unicode 15.1 lowercase to both query and complete title. Match is a literal substring; no casefold, accent folding, NFC/NFKC, SQL wildcard, ranking or browser Unicode-version parity. Raw query is at most 256 code points; NUL rejects before PostgreSQL. A normalized query longer than 240 cannot match, while cursor validation still applies. A private derived key is backfilled by migration 0020 and updated atomically on create, first-admission auto-title and rename under the existing thread-lock ownership. Future matcher/Unicode changes require explicit backfill and cursor-version treatment.

Search cursor v2 binds Account, normalized query, matcher version and exclusive created-time/ID boundary. Invalid, foreign, changed-query/version or mixed ordinary/search cursors return `invalid_thread_cursor`; no cursor grants authorization. Ordinary v1 pagination is preserved.

Nonempty searches use two nonblocking permits per API process before pool checkout, released in `finally` on every path. Ordinary history bypasses this admission. After normal auth and cursor validation, PostgreSQL search SELECT uses transaction-local `statement_timeout=1000ms`. Permit refusal, pool TimeoutError and PostgreSQL 57014/55P03 become 503 `search_unavailable` after transaction rollback, without partial results, SQL disclosure or automatic retries. Other errors and shared auth/engine behavior are preserved. This does not promise fleet fairness or a total HTTP deadline.

The sidebar uses separate history and search rows, cursors, loading/error state and scroll. Clearing search restores loaded ordinary pages. Abort plus Account/query/generation/request fences discard stale success and failure. Rename confirms membership against the server without destroying its active form. Existing thread opening preserves branch/attempt selection and messages. Keyboard, touch, mobile drawer, focus and scroll remain part of acceptance; query text is ephemeral.

## Finite writer ownership

The manifest allows 32 exact paths, `cross_domain`, high risk, independent review required. Backend owns fourteen paths including API, private migration, tests and one additive PostgreSQL CI step. Frontend owns eight paths in the existing sidebar/runtime and focused browser tests. Browser QA owns two real acceptance paths. Controller owns eight orchestration/documentation/generated-contract paths; all four canonical state paths are native-tool-only, with CHECKPOINTS expected unchanged.

Every writer receives the DEVELOPMENT task contract, a separate worktree/branch, the same integrated decision base, explicit non-goals and its own path list. No path has two active writers. Read-only independent review remains separate from implementation and fixes.

### Explicit PostgreSQL CI invocation

The existing `tests/test_chat_graph_migration.py::run_postgres` is a standalone runner and is not invoked by the current workflow. Merely adding another import would not prove PostgreSQL execution. The only workflow change adds a required isolated PostgreSQL 17 acceptance step after Container integration, using the already pulled image, synthetic credentials, a loopback random port, health barrier and guaranteed container cleanup. It runs the new standalone test owner from the host development environment. Existing assertions, skips, retries, timeouts and gates are unchanged; the new step has its own five-minute bound. No production Compose, runtime image or dependency changes are authorized.

## Acceptance and evidence boundaries

Targeted server tests cover complete history, Account isolation, exact query bounds/normalization/Unicode, literal wildcard characters, no-result/empty input, cursor misuse and stable tie-breaking across more than 100 matches, concurrent create/rename, derived-key migration/atomicity and capacity/timeout/rollback behavior. PostgreSQL proves actual SQL behavior, query cancellation, released auth locks, restored transaction-local timeout and retry after recovered capacity.

Playwright covers fast query changes, held API responses and abort, stale errors, first/next-page retry, Account changes, preserved history pages/cursor/scroll, rename, Graph result opening, reload/login, focus and mobile interactions. Real isolated Compose and clean-preview acceptance seed at least 151 threads in dedicated synthetic accounts, find rows beyond the first two pages and preserve selected branches/attempts before and after retained-volume restart. No paid model calls are permitted.

The separately published focus-test repair PR #278 is not merged into this package and does not alter its runtime. Its controlled reproduction and independent review remain separate technical-debt evidence. Existing CI retry policy is unchanged.

## Implementation status at initial decision commit

Implementation, generated-contract update, targeted tests, integrated gates, independent technical review, real browser/PostgreSQL evidence and exact published-source required CI are pending. This document establishes the accepted bounded contract and writer ownership; it does not claim completed code or PASS results.

Focused contract review found one concrete CI readiness race: the official PostgreSQL entrypoint first serves a temporary Unix socket. SEARCH-CI-001 requires the new container health check to use `pg_isready -h 127.0.0.1 -p 5432` before the host TCP runner starts. The backend writer must apply this correction; independent review will verify the actual diff. No runtime PASS is claimed by the static review.
