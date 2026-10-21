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

The initial manifest allowed33 exact paths, `cross_domain`, high risk, independent review required; the documented SEARCH-CI-003 extraction increases this to35 exact paths within the unchanged class limit40. Backend owns fourteen paths including API, private migration, tests and one additive PostgreSQL CI step. Frontend owns eight paths in the existing sidebar/runtime and focused browser tests. Browser QA owns three real acceptance paths. Controller owns eight orchestration/documentation/generated-contract paths; all four canonical state paths are native-tool-only, with CHECKPOINTS expected unchanged. Fix assignments below transfer exclusive ownership of frozen paths for bounded repairs.

Every writer receives the DEVELOPMENT task contract, a separate worktree/branch, the same integrated decision base, explicit non-goals and its own path list. No path has two active writers. Read-only independent review remains separate from implementation and fixes.

### Explicit PostgreSQL CI invocation

The existing `tests/test_chat_graph_migration.py::run_postgres` is a standalone runner and is not invoked by the current workflow. Merely adding another import would not prove PostgreSQL execution. The workflow adds a required isolated PostgreSQL 17 acceptance step after Container integration, using the already pulled image, synthetic credentials, a loopback random port, health barrier and guaranteed container cleanup. It runs the new standalone test owner from the host development environment. Existing assertions, skips, retries, timeouts and gates are unchanged; the new step has its own five-minute bound. The bounded two-account test configuration below is also permitted. No production Compose, runtime image or dependency changes are authorized.

## Acceptance and evidence boundaries

Targeted server tests cover complete history, Account isolation, exact query bounds/normalization/Unicode, literal wildcard characters, no-result/empty input, cursor misuse and stable tie-breaking across more than 100 matches, concurrent create/rename, derived-key migration/atomicity and capacity/timeout/rollback behavior. PostgreSQL proves actual SQL behavior, query cancellation, released auth locks, restored transaction-local timeout and retry after recovered capacity.

Playwright covers fast query changes, held API responses and abort, stale errors, first/next-page retry, Account changes, preserved history pages/cursor/scroll, rename, Graph result opening, reload/login, focus and mobile interactions. Real isolated Compose and clean-preview acceptance seed at least 151 threads in dedicated synthetic accounts, find rows beyond the first two pages and preserve selected branches/attempts before and after retained-volume restart. No paid model calls are permitted.

The separately published focus-test repair PR #278 is not merged into this package and does not alter its runtime. Its controlled reproduction and independent review remain separate technical-debt evidence. Existing CI retry policy is unchanged.

## Implemented source and pre-publication evidence

Frozen Backend `c3a6e583f15fbc91308a48aabb2ff0cc66b71c3c`, Frontend `be4bea825af54afc157255e9a5d475a27d24323f` and Browser QA `374cb14263421e1513e28c571b4a5c49815d8a37` are integrated without component drift. OpenAPI adds only optional bounded `q`. Controller SELF_REVIEW covers ownership, cursor/transaction races, unchanged Graph execution, scope and evidence provenance.

Backend:131 targeted tests passed; two affected migration tests were rerun after stronger index assertions. Real PostgreSQL17.11:8 named cases passed, plus that strengthened migration recheck. Frontend:154 affected regressions passed before a narrow current401 cleanup; all16 search cases passed on final source. Chromium140/rev1193 is diagnostic, retries0; pinned149 fullCI remains mandatory. Integrated production build, native state verify, docs, scope, hygiene, generated contract and diff checks passed.

Maintenance:31/33 scoped paths; root context4164 B, PLAN1809 B; API/Web local READMEs5969/5753 B. No changed handwritten file is in the warning zone. Sidebar/runtime have2/20 B remaining before the unchanged80% byte threshold; further growth requires owner separation. New search owners keep query work separate from Graph/history; live-entry split reduces its size. Full per-file dimensions/headroom and independent review receipts accompany the PR.

Independent review found only the isolated admission blocker below; separate Fix Implementer commit `c29bf41e118ab26a2ce97b76bc5b000581c58b57` preserves all other workflow bytes. Actual HTTP proof:6 before and6 after cases, including a still-denied third account. Final re-review and exact published-source CI/real Compose evidence are recorded on the PR; they are not predicted by this pre-publication record. Internal review is not formal GitHub APPROVED.

Focused contract review found one concrete CI readiness race: the official PostgreSQL entrypoint first serves a temporary Unix socket. SEARCH-CI-001 requires the new container health check to use `pg_isready -h 127.0.0.1 -p 5432` before the host TCP runner starts. The backend writer must apply this correction; independent review will verify the actual diff. No runtime PASS is claimed by the static review.

## Reviewed acceptance-owner split before the extra path

The complete seven-scenario browser acceptance candidate measured 14581 B / 239 lines; the existing live entry measured 13094 B / 252 lines against a 12794 B baseline. Its original six-byte growth margin cannot accommodate the required invocation and context reuse. The controller inspected the lifecycle, shared UI helpers and legacy rename sequence before approving one additional path.

`chat-thread-search-live.mjs` owns isolated account setup, seed/provenance and retained restart orchestration. `chat-search-ui-live.mjs` owns reusable public UI paging, focus/scroll, rename and Graph assertions. The existing entry imports a compatible rename helper while retaining its visible-title assertion and all original calls. Browser QA is the sole writer of all three paths; no product owner, workflow or dependency is added. The manifest now permits 33 exact paths, within the unchanged cross-domain40 limit. Each new auxiliary owner must remain at or below12800 B/280 lines, and the existing entry must regain space below12800 B. No test assertion, runtime check, retry, timeout or size threshold is relaxed. Independent review must verify the actual extraction and coverage equivalence.

## SEARCH-QA-002 — isolated account admission correction

Independent integrated review found that the live fixture registers `search@local.izo`, while both existing CI stacks admit only `preview@local.izo`; the first seed POST would fail with403. Before any fix, the controller explicitly permitted the already-scoped `ci.yml` to admit these two exact synthetic addresses in the Container integration step and the clean-preview temporary environment. Compose interpolation already accepts this configured value. Bootstrap, preview-builder defaults, production Compose and the ChatService admission guard remain unchanged. The separate Fix Implementer owns this one-path correction; the reviewer must verify it and the real CI must execute it. No new scope path or account/permission owner is introduced.

## SEARCH-CI-003 — required workflow modularity repair

The first published source `b9e811e7344155ca92d82c647c330b3ae0dd89a2`, tree `291ffc34d9ae2b24a8c93386cf92946e84fe2b05`, failed Foundation CI39558102453 at the existing `test_ci_workflows_stay_modular`: ci.yml is17703 B against an unchanged16000 B limit. Actual unit results were1485 passed,1 failed,1 skipped; browser, PostgreSQL acceptance and both real preview stacks did not run. Security39558102127 and Review Source39558102272 passed. Acceptance remains blocked until a corrected exact source passes all required CI.

Before assigning writes, the controller inspected the added41-line PostgreSQL orchestration and the established tool/test owners. Extract that cohesive disposable-container responsibility into `tools/chat_thread_search_postgres_ci.py`, tested by `tests/test_chat_thread_search_ci.py`; ci.yml retains its five-minute step and invokes it with the existing isolated environment. This adds two exact paths (35 allowed,33 expected changed), below the unchanged cross-domain40 limit, and explicitly approves the new tool as sensitive. It is responsibility separation, not a budget increase or assertion change. The separate Fix Implementer alone owns the workflow and these two new paths; controller alone owns this record and the manifest.

Preserve PostgreSQL17 image reuse without pulls, loopback ephemeral port, TCP health barrier,45 readiness probes, original health settings, synthetic credentials and the existing standalone eight-case runner. Add guarded environment validation, cleanup of only the created container, failure propagation and cancellation cleanup. Prove healthy/unhealthy/expired readiness, runner failure and cancellation behavior with isolated subprocess fixtures; actual Docker execution remains a required CI condition. All other workflow bytes, including the two-account admission correction, remain unchanged. Do not alter retries, timeouts, architecture limits, tests, dependencies or canonical state. Independent review must check the extraction and exact-source binding before a new complete CI run.

## SEARCH-REVIEW-004 — burst typing and server admission

GitHub COMMENTED review5595979460 on the first published exact source raised P1 discussion4333878653: aborting a browser fetch does not cancel the synchronous server handler. Immediate search on every keystroke can occupy both process permits while the latest valid text receives503. The controller accepts this bounded UX/load finding for correction; it is not a formal GitHub approval.

The Frontend Implementer owns an isolated fix in the existing `useThreadSearch.ts`, search spec and fixture paths. Cancel/fence obsolete responses immediately, debounce dispatch of newly typed text by300ms, and clear pending timers on query, account, reset and unmount changes. Pending search must show loading without stale rows or an empty-result flash. Manual retry, pagination and confirmed Rename refresh keep their explicit behavior. Strengthen rapid-input/slow-response/account tests without changing test retries, assertions or timeouts, and retain the prior regression coverage. The independent reviewer checks the actual fixed source and evidence; full required CI on the combined corrected source remains mandatory.
