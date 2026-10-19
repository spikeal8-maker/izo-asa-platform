# P1-CONVERSATION-GRAPH-001

Status: active after the genuine successor transition. Implementation and local validation are committed; required PR CI and exact-source acceptance remain separate gates.

## Goal and canonical source

Add "Ответить заново", durable response variants, selection of completed variants and execution context
from selected responses inside the existing Chat domain. The owner selected this package after rename closeout.
The accepted base is `e637017111fcea0ec4ad6291ac700f8baa90a270`, the ordinary merge of
[PR #272](https://github.com/spikeal8-maker/izo-asa-platform/pull/272).
Its ordered parents are `13c8240ed7b49028b7e479b3870aaf97e68f9654` and
`a26f74e693be7ed617bb8aed221be89cd4760876`; its tree is `69811c1a05cb552cf1fc810ee97407f5b8ac1db7`.

The narrow source audit read `ARCHITECTURE` section 10, `AI_RUNTIME` section 11, `UX` section 10,
the existing Chat owner maps, admission/execution/history code and adjacent tests.
The canonical contracts already define regeneration, immutable turns, completed-only selection and the selected context path.
This slice implements those decisions; edit-as-new-branch and a general Context Engine remain outside its boundary.

## Accepted predecessor evidence

The owner authorized only exact PR #272 source `a26f74e693be7ed617bb8aed221be89cd4760876`.
The actual [seven-line waiver](https://github.com/spikeal8-maker/izo-asa-platform/pull/272#issuecomment-6264491084)
was published and read back from `spikeal8-maker` at `2026-10-19T09:53:27Z`, before normal merge at `09:54:18Z`.
It binds the three successful PR workflows: Foundation `39226673674`, Dependency `39226673632`, Review Source `39226673818`.

New push/main checks on the actual merge passed independently:

| Gate | Actual result |
| --- | --- |
| [Foundation CI 39233532197](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/39233532197) | SUCCESS, attempt 1; verify 117997001499 and Windows 117997001855 |
| [Dependency Security 39233532168](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/39233532168) | SUCCESS, attempt 1; npm audit 117997001552 |
| Python | 1378 passed, 1 skipped, 3 warnings; 239.01 seconds |
| Browser | 880 passed, 391 skipped; 1271 unique results, every retry 0; zero extra attempts, flaky results or errors |
| Rename matrix | All 80 cases across 10 viewports passed |
| Persistence | Actual container and separate clean-preview before/down/up/after cycles; volumes retained between assertions |
| Visual review | QA, independent reviewer and controller personally viewed three new desktop/mobile PNGs; PASS |

The new browser artifact `12178751863` was downloaded and independently verified: 13,515,495 bytes,
SHA-256 `79452c7115a1ea097f43cc2cc5d09085f488b5e62c12198f74f7d20a1e8244d2`.
Full QA provenance is 46,005 bytes, SHA-256 `a6654751487230306d592fba870a7cdd31cabf650ca3eae98b5957e78fe75b93`.
The independent reviewer challenged all 22 manifest files, actual workflow/log identity, the HTML report and all three images.
The large preview archive was metadata-only for local QA; its clean execution and restart really ran in CI.
Independent post-merge verdict: APPROVE, no blocking findings. These results validate the predecessor, not the new Graph code.

## Genuine state activation

The controller fast-forwarded the preserved canonical branch to the actual accepted main; checkout and state verification passed.
The actual repository command then completed with exit 0:

```sh
python -B tools/project_state.py --github-transport connector-stdio begin-decided-next \
  --branch codex/p1-conversation-graph-001 --activate P1-CONVERSATION-GRAPH-001 \
  --goal "Regenerate answers in the existing Chat domain, persist immutable turns and response attempts, switch completed variants, and freeze request context from the selected answers while preserving ownership, history and mobile usability." \
  --depends-on P1-CHAT-THREAD-RENAME-001 --decides-next --verified-pr 272
```

The live bridge forwarded 83 fresh Connector requests, including the workflow's final mutable-evidence revalidation.
The saved unmodified request/tool/response transcript is 7,266,152 bytes,
SHA-256 `f5179fab0a64f1e7571aa9cd987e6d0adad4365c5b8f170184bea35a28a510a7`.
Actual output: `STATE STARTED: active=P1-CONVERSATION-GRAPH-001 branch=codex/p1-conversation-graph-001`.
The workflow wrote `PLAN.json`, `PACKAGES.json` and `CURRENT.md`; all 28 checkpoint records and the complete
`CHECKPOINTS.json` bytes remained unchanged, as did all previous package records. State verification and whitespace checks passed.
The before/after records have SHA-256 `76c0e0f748c298210028c75e1abe08fed732919ceae6d94e42f7f06ef902df84`
and `ee69c95a5dc5f550e7637011ecee468f91e0e6cd8ddcb6ff14788c402299f0ae` respectively.

## Ownership and task graph

The [finite scope](../../tools/scopes/p1-conversation-graph-001.json) is cross-domain, high risk,
40 allowed paths under the unchanged hard class limit of 40. Independent review is mandatory.

- Controller: actual state workflow, scope, this report, task contracts, integration and acceptance evidence.
- Backend implementer: 20 assigned Chat/migration/contract/test/architecture paths.
- Frontend implementer: 15 disjoint Chat UI/browser/acceptance/UX paths.
- QA: independent actual PostgreSQL, HTTP, browser and restart verification on the integrated source.
- Independent reviewer: read-only code, race, ownership, data, documentation, test and responsive review; findings return to the assigned writer.

Backend and frontend receive separate worktrees and the complete thirteen-field task contract before write GO.
Implementation precedes integration; integrated targeted gates precede source freeze, exact-head review and full required CI.
An internal technical review does not replace the separate structured GitHub approval or an authorized waiver needed for acceptance.
The owner's PR #272 waiver does not authorize merging this future feature PR.

Before creating the additional `useConversationGraph.ts` path, the frontend requested a scope amendment.
The controller reviewed the unchanged `web.chat` boundary, the existing 6017-byte / 133-line selection owner and
the otherwise combined DTO/cache/revision/command responsibilities. The amended assignment separates Graph projection
and loaded-page fences from attempt commands/replay, adds one exclusively frontend-owned path and keeps the hard limit unchanged.

A second amendment was requested before creating `conversation-graph-races.spec.ts`.
The existing basic Graph specification was 12,614 bytes, close to its unchanged 12,800-byte creation budget.
The newly identified unloaded-turn/late-page lifecycle scenario belongs with the existing revision and response-order
races. The controller approved moving those cases to one separate race specification before adding the regression,
leaving basic regenerate, replay and controls in the original test owner. This adds one frontend path (15 total)
without raising any file-size or class limit. No CI workflow path was added; the existing Chat live acceptance hook
already executes real Graph HTTP races and both restart cycles in required CI. The separate SQL-lock runner requires
independent PostgreSQL execution and is not represented as a default CI test.

## Agreed implementation boundary

Physical message IDs, sequences and existing message-history cursors retain their contracts.
A version marker on ThreadDetail selects an additive Graph projection with immutable turn cursors, bounded at 50 turns.
The attempt-history endpoint is bounded at 20 attempts and always includes the fresh selected turn state.
Regenerate POST includes request ID, branch, selected source attempt and expected revision; selection uses PATCH with fresh revision CAS.
Completed-only previous/next IDs and positions support the selector without loading unbounded variant history.

The old completed response remains selected while a new attempt runs or fails.
Only durable completion atomically selects the new response; selection/revision reads are coherent under PostgreSQL READ COMMITTED.
Thread-before-request row locking applies consistently to admission, claim, partial writes and completion.
Attempt lifecycle is derived from existing ChatRequest, preserving credential-disable, expiry and restart recovery behavior.
Exact request-ID replay retains idempotency; UNKNOWN outcomes block new execution until reconciliation.

Each admitted send/regenerate freezes the selected prefix; regeneration of an earlier turn excludes its alternatives and later turns.
Legacy claim snapshots have honest claim-time provenance. Forward migration retains existing IDs, messages, attachments,
manual titles and physical sequences, with same-thread foreign keys for new graph relations.
The frontend keeps stable turn DOM anchors, focus, scroll, selected chat and loaded history pages, and rejects stale revisions.
New controls remain available on keyboard, desktop and mobile using the existing design.

## Validation and maintenance delta

The following records bind actual results to their tested local source. PostgreSQL and browser gates have executed;
required PR CI and both container restart cycles must also pass on the published merge tree. Coverage includes ownership/CSRF, migration retention,
completed-only selection, stale CAS, concurrent admission/completion/selection, exact replay, UNKNOWN, selected-context snapshots,
old-turn pagination, stale browser responses, focus, mobile controls and durable selection after reload/restart.

New graph owners separate storage, commands, projection, context and UI attempt control from existing near-limit runtime files.
Local owner maps are updated when boundaries change. Hard size, line and scope limits remain unchanged.
Detailed actual commands, results, review findings and final source evidence are recorded at integration.

### Incremental implementation and independent findings

The backend writer created isolated commits `087fa48421c54fec27772eb37499fe432b7b70b7`
(schema/backfill/context), `e83c4f523b6a941066e166b4ec157263de573f9a` (independent findings),
and `09adff889ff1979d45f7c46f375e8bd534b219fa` (commands, projection, execution, HTTP, tests and contracts).
The independent reviewer inspected frozen worktrees and did not edit the reviewed source.

| Finding on the first schema commit | Writer correction and independent result |
| --- | --- |
| A request context could name a different turn in the same thread | Composite foreign key now binds request, turn, branch and thread to the exact assistant attempt; the original SQL counterexample is rejected |
| Captured snapshot revision accepted SQL NULL through a nullable CHECK expression | Explicit non-null check; NULL and negative revisions fail for both admission and legacy-claim provenance, while revision zero succeeds |

Independent bounded verdict on exact `e83c4f523b6a941066e166b4ec157263de573f9a`: APPROVE.
The reviewer reran all six migration tests (exit 0, two existing deprecation warnings), reproduced the rejected
counterexamples, compared runtime DDL with the frozen migration and verified that honest legacy-unrecorded rows
were unchanged. This is SQLite with foreign keys enabled; it does not establish PostgreSQL concurrency or accept
the full feature. The review receipt has SHA-256 `0753f421b31fa2c03b16d77cc9c89d49a0bcdfd4db5f07af0d0e4f83d6b7ff86`.

The backend writer's wider Chat/catalog run initially returned 142 passed, one skipped and one failed.
The failure exposed an existing indistinguishability contract: a preliminary lookup of a foreign request ID must
not precede current catalog resolution. The writer restricted that preliminary replay lookup to the owner;
the ordinary conflict check remains after catalog resolution. The previously failing regression plus all four
new Graph suites then returned 37 passed, exit 0. The original failing result is retained as evidence.
Those intermediate results did not establish PostgreSQL concurrency, live restart or full integrated-source acceptance.

The controller integrated the accepted backend history using ordinary merges. On exact local
`b9ae27166c61ef7d55b09e95f9afc7fba151e02f`, the full Python suite actually returned **1414 passed, one skipped,
three existing warnings**, exit 0, 291.26 seconds. State verification, docs, generated OpenAPI, hygiene, finite scope
and whitespace gates also passed. The saved receipt has SHA-256
`e69eae88134ff0b25c17f064c433f6f7b9507322a180aea7b77dbf2b302a9e2d`.
The later backend commit `c7bebc8b74fa41b8cdcf5653dc29d0bc045fbb12` adds a thirteen-case standalone PostgreSQL
runner inside the four assigned tests. Default Graph tests on that commit returned 36 passed; its subsequent real
PostgreSQL failure, correction and independent verification are recorded below.

Frontend core `105b086a0cdc63ca17fbf6e71ef48ef68674b572` includes generated wire-type aliases and the normal
Graph controls/projection. Its ten-viewport Graph matrix returned 162 passed and eight expected skips, exit 0,
with every retry zero. Before that pass, a deterministic browser test reproduced an old same-revision response
restoring pending state after observed termination. The writer's lifecycle witness fixes that case; the original
two failing cases were retained, and all eight targeted terminal-state cases then passed.
Combined product core `d4689bc16ff889e65699b8cd6bdc32570efe913d` was frozen for the full browser run and an
independent read-only review. Live acceptance, a further unloaded-turn race and the final integrated source are
not accepted by these intermediate results.

### Integrated browser and lifecycle corrections

On exact combined core `d4689bc16ff889e65699b8cd6bdc32570efe913d`, the controller actually ran the ordinary web
build and full Playwright suite: **1042 passed, 399 skipped**, 1441 results, exit 0, 8.6 minutes, every retry zero.
The web receipt SHA-256 is `ba5734aec9e7e0a8e5024ded8d67dbfde807ab0a67112d36ce6f7bb7796e0eae`.
The independent reviewer nevertheless found an uncovered late-SSE defect; this green suite did not close that finding.

| Reproduced finding | Correction and real regression result |
| --- | --- |
| Late SSE delta/error could corrupt a response already confirmed completed by Graph | Frontend `e1c75669020d865948c1972501daf89799fc50b4` guards initial clearing, deltas and late errors with terminal authority; two browser failures preceded the successful regression |
| A late older page could introduce an off-page turn without its already observed terminal lifecycle | The same commit retains observations independently of loaded pages and refreshes the active turn before publishing its page; six failing interrupted/error/stopped cases preceded PASS |
| The live helper expected an event absent from the actual SSE contract | `548b0345986667999de1b93aa69a64d581b9ba80` changes helper and fixture assertions to the real `message.done`; six targeted browser cases passed |
| A legitimate streaming paid-submission marker was incorrectly promoted to terminal UNKNOWN, preventing SSE resume | `c5e32286bfc081cbf9e87b1afb64b158ab03c083` checks lifecycle in both page and turn merges and prioritizes active UI status; four phone/laptop reload/replay failures preceded 26 passing related cases |

The last finding was independently demonstrated with both production frontend functions and real synthetic Chat execution:
`state=streaming`, `error_code=provider_outcome_unknown`, `unknown_request_id=null` is a valid active server state.
The corrected fixture now follows that lifecycle, including marker retention after stop/interruption and clearing after
completion or a known rejection. New browser checks require the same request UUID to resume, without another admission POST;
genuine terminal UNKNOWN still blocks new execution after reload.

Final frontend source `c5e32286bfc081cbf9e87b1afb64b158ab03c083` actually passed:

- **198 passed, 32 skipped** in the complete Graph matrix across ten viewports, exit 0, 1.9 minutes, retry zero.
  The 32 skips are four 53-turn scenarios restricted to phone-small and laptop; those two viewports really executed them.
- **12 passed, two skipped** in the nearest legacy resume/UNKNOWN/partial-copy checks, exit 0, 8.8 seconds.
- The earlier shared-hook regression on `e1c7566` covered twelve adjacent suites: **110 passed, 20 skipped**, exit 0.
- Final typecheck/build, docs, hygiene, scope and whitespace checks passed. Its generated type dependency was the
  unchanged backend OpenAPI on `31c4dd1a982892aa81b7ceebd28d8e92bb102098`.

The retained paid-marker RED, targeted GREEN, complete matrix and nearest-legacy logs have respective SHA-256 values
`2fab0ba75fd525781b85abdf47221587297db675ce79ccbb4b83a05958d2a30d`,
`73c68a7a15706bff2872d028a8e31b2d67096975ee8a2c36f504da013c72ceb7`,
`dd00b1ea0edf9c027281c0239a84379f5ce91be21314b3563c2a8c54df5535d8` and
`6874a67c05f9d83485ff027c0022df5021f6980c038a5e408ec55c3d88a7eb83`.

### Actual PostgreSQL 17 proof

The first independent run on `d4689bc16ff889e65699b8cd6bdc32570efe913d` failed at the first migration-retention
case with `CatalogError(503, catalog_unavailable)`; **zero** PostgreSQL cases passed. Its original proof remains preserved
with SHA-256 `7e4530fec9487fd11d83f195bb6f0b76fb2bf5e3541529e9ce297ec9a39aa61b`.

The backend writer confirmed a fixture defect: metadata created empty catalog tables, while runtime test seeding
intentionally applies only to SQLite. Commit `24bc3e18dd2679e99fddf1068018b796538eef84` changes only the two assigned
test files so PostgreSQL catalog tables, seed and audit triggers come from the real, unchanged `0013_admin_catalog`
migration inside the scenario's isolated UUID schema. Admission, permissions, runtime, constraints and test assertions
remain unchanged. The writer reproduced RED, then ran all thirteen PostgreSQL cases successfully and nineteen ordinary
migration/HTTP tests successfully, exit 0.

After ordinary integration, independent QA actually reran all **13 cases: 13 passed, zero failed, zero skipped**, exit 0,
13.484 seconds, on exact `4098fc61ac83a7a34c74bba3681e71f3117a9fbc`, tree
`f0a812e14ea923ee164d2f033f2430ab5e03f975`. The server was PostgreSQL **17.11**, READ COMMITTED,
`fsync=on`, `synchronous_commit=on`, listening only on loopback. All requests used synthetic providers and isolated data.

The unchanged SQL observer recorded seven actual blocking snapshots, including three simultaneous Thread waiters,
a successful Request `FOR UPDATE NOWAIT` while completion waited for Thread, six expected FK SQLSTATE `23503`
failures and two expected CHECK `23514` failures. Retained IDs/messages/attachments/manual titles, exact replay,
completed-only selection in both commit orders, frozen selected context, earlier-turn exclusion, stop/late partial,
known rejection and UNKNOWN barriers passed. Schemas before and after were both empty; source files remained unchanged.

Independent proof SHA-256: `41396abc39a42e5332334f8e324e97f86fd9f77b47859efaca613677f3e41f80` (14674 bytes).
Independent QA review: `e5b3d8996ad6ec62d6a838473a1dda4a8013e84cfcfb75d08513e0c9b3d6167c` (6698 bytes).
Full runner log: `b68b4cd53b140ae92b99b21392e13501cdee05412d1938198ebc42b6522a3ef0` (6965 bytes).
The separate reviewer challenged 37 source hashes, eight additional hashes, the unchanged thirteen-case AST and lock
chronology, and approved this bounded correction. Its receipt SHA-256 is
`ace19efc5a5d4ead4b7d0d17ce5fe32a404dfff20a488c348ce3c3dc8c8f7a6e` (5363 bytes).

This is service-level verification on real PostgreSQL. It does not claim that the standalone SQL runner is a default CI
stage or replace the separate HTTP/browser/Compose before-and-after restart acceptance.

### Final local integration

Both writers' complete histories were integrated by ordinary merges into
`74b06e2157792e8b4942de9add821d42e233c4a5`, tree `3b287d41a92e33282546031391ededdab3d5cb91`.
The controller then ran the ordinary `npm run build` against the actual combined backend OpenAPI, plus state verification,
docs, generated contracts, repository hygiene, the forty-path scope and whitespace gates: every command exited 0.
The exact receipt has SHA-256 `16cc8565555bfa939778d7ee6562fd349046fd4a95a5cd9145cdc41ca81432e3`.
All state files still equal the genuine activation outputs; all checkpoint bytes still equal accepted main.

Independent technical source verdict on that exact `74b06e2157792e8b4942de9add821d42e233c4a5`: **PASS**,
with no blocking findings remaining. The reviewer reran thirteen focused checks against the actual production
Graph/stream functions, separately reproduced the real synthetic Chat streaming marker and successful completion,
bound the tested frontend bundle to the integrated build, and challenged the PostgreSQL and browser evidence.
The final source review receipt is 14234 bytes, SHA-256
`2ee50198d70907e7b7a397336fd0c45068cec1be74f3772a7355067043816e7e`.
It is an internal independent code review, with published-source identity, required CI, real restart artifacts and
the repository's separate GitHub approval/owner-waiver gate still required for final acceptance.

Publication preserves every implementation commit's tree and ordered parent edges. Connector-created commit author and
committer metadata can produce different Git SHAs; the controller records the complete local-to-published mapping and
checks the actual Git objects and final branch. The published source therefore requires its own exact-source review and
full required CI on the actual PR merge tree. Final run IDs and immutable artifact verification belong in that PR's
evidence, without changing an already tested source solely to add its own CI IDs.

### Final maintainability delta

The package changes 40 approved paths, including 30 handwritten code/test files. No changed near-limit owner
grew, no hard or creation limit was raised, and no new dependency or workflow/protection change was introduced.
Root initial context is 4165 bytes; live plan is 1811 bytes. Initial `api.chat` context is 7819 bytes and
`web.chat` is 8748 bytes. The backend owner README is 5801 bytes (base 5110); frontend README is 5704 (base 5743).

The table reports final dimensions and remaining hard-limit room. New owners additionally remain below the
unchanged 80% creation threshold. Existing near-limit modules were not expanded; Graph storage, context, projection
and attempt commands have separate owners, while the existing Chat entrypoints continue to delegate to them.
The complete measured maintenance record has SHA-256
`bc163c5068b69986f25157ae6453d6e33e79b95a460a35ef9dbc6cb6aee07a2f`.

| Handwritten file | Bytes | Lines | Free bytes / lines |
| --- | ---: | ---: | ---: |
| `apps/api/izo/chat/conversations.py` | 5531 | 99 | 6469 / 201 |
| `apps/api/izo/chat/execution.py` | 8232 | 210 | 3768 / 90 |
| `apps/api/izo/chat/graph_context.py` | 6757 | 135 | 5243 / 165 |
| `apps/api/izo/chat/graph_requests.py` | 7802 | 143 | 4198 / 157 |
| `apps/api/izo/chat/graph_routes.py` | 2012 | 37 | 9988 / 263 |
| `apps/api/izo/chat/graph_schemas.py` | 1951 | 81 | 10049 / 219 |
| `apps/api/izo/chat/graph_selection.py` | 6463 | 140 | 5537 / 160 |
| `apps/api/izo/chat/graph_tables.py` | 5949 | 84 | 6051 / 216 |
| `apps/api/izo/chat/history_pages.py` | 9307 | 158 | 2693 / 142 |
| `apps/api/izo/chat/request_state.py` | 5987 | 133 | 6013 / 167 |
| `apps/api/izo/chat/routes.py` | 8580 | 237 | 3420 / 63 |
| `apps/api/izo/chat/tables.py` | 7953 | 128 | 4047 / 172 |
| `apps/api/migrations/versions/0018_chat_conversation_graph.py` | 10102 | 150 | 5898 / 200 |
| `apps/web/acceptance/chat-graph-live.mjs` | 12085 | 182 | 3915 / 168 |
| `apps/web/acceptance/chat-live.mjs` | 10373 | 212 | 5627 / 138 |
| `apps/web/e2e/conversation-graph-fixture.ts` | 10919 | 172 | 5081 / 178 |
| `apps/web/e2e/conversation-graph-races.spec.ts` | 10505 | 171 | 5495 / 179 |
| `apps/web/e2e/conversation-graph.spec.ts` | 8080 | 140 | 7920 / 210 |
| `apps/web/src/shell/ChatPage.tsx` | 7897 | 171 | 4103 / 129 |
| `apps/web/src/shell/chat/ChatMessage.tsx` | 7779 | 148 | 4221 / 152 |
| `apps/web/src/shell/chat/ChatRenderer.css` | 2378 | 26 | 9622 / 274 |
| `apps/web/src/shell/chat/streamChatRequest.ts` | 3225 | 61 | 8775 / 239 |
| `apps/web/src/shell/chat/useAssistantAttempts.ts` | 8377 | 140 | 3623 / 160 |
| `apps/web/src/shell/chat/useChatRuntime.ts` | 9140 | 191 | 2860 / 109 |
| `apps/web/src/shell/chat/useConversationGraph.ts` | 8436 | 137 | 3564 / 163 |
| `apps/web/src/shell/chat/useThreadSelection.ts` | 7001 | 151 | 4999 / 149 |
| `tests/test_chat_graph_context.py` | 11993 | 218 | 4007 / 132 |
| `tests/test_chat_graph_http.py` | 11637 | 232 | 4363 / 118 |
| `tests/test_chat_graph_migration.py` | 12679 | 241 | 3321 / 109 |
| `tests/test_chat_graph_requests.py` | 12497 | 231 | 3503 / 119 |
