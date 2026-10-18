# P1-CHAT-THREAD-RENAME-001 — isolated implementation candidate

## Authority and status

On 2026-10-18 the owner explicitly authorized implementation, tests and independent review on isolated candidate worktrees while the canonical state transition is unavailable to the local CLI. This candidate does not change PLAN, PACKAGES, CURRENT or CHECKPOINTS and does not claim package acceptance.

- Target repository: spikeal8-maker/izo-asa-platform.
- Approved source base: 5b198dc5d20cc0ce703272a7a2f4b2a0bbf587dc.
- Functional task: https://github.com/spikeal8-maker/izo-asa-platform/issues/268.
- Product order: https://github.com/spikeal8-maker/izo-asa-platform/issues/222.
- Scope class: cross_domain; risk: high; finite file cap: 32.
- Backend, frontend, local integration and independent review are complete. Publication and exact-head CI are recorded in the candidate PR.
- Merge, deployment, paid provider calls and canonical checkpoint acceptance are outside this candidate authorization.

## SOURCE_AUDIT — FULL

The read-only source audit preceded implementation and was retained from the initial handoff. Target contracts take priority over donor behavior.

Canonical owners: AGENTS.md, docs/CURRENT.md, DEVELOPMENT.md, MAINTAINABILITY.md, PRODUCT.md, UX.md, ARCHITECTURE.md and AI_RUNTIME.md. Local owners are the API Chat and web Chat README files.

Observed target source at the approved base:

| Owner | Observed behavior | Implementation decision |
|---|---|---|
| apps/api/izo/chat/routes.py | Existing shared mutation guard; no rename endpoint | Reuse origin, session and CSRF checks for PATCH |
| apps/api/izo/chat/schemas.py | ThreadView already owns public thread metadata | Return the existing ThreadView; validate a strict title-only body |
| apps/api/izo/chat/tables.py | title is VARCHAR(120); no manual-title intent | Add one private durable Boolean through a forward migration |
| apps/api/izo/chat/conversations.py | First-message admission locks the thread and may replace the default title | Serialize rename with the same lock and respect manual-title intent |
| apps/api/izo/chat/thread_pages.py | Cursor/order use immutable created_at,id | Rename must leave both fields unchanged |
| apps/web/src/shell/chat/ChatSidebar.tsx | Thread rows open conversations; no rename control | Add a separate accessible action and bounded editor |
| apps/web/src/shell/chat/useThreadHistory.ts | Refresh replaces the first page and clears paging | Apply the confirmed title to one existing row and fence stale reads |
| apps/web/src/shell/chat/useChatRuntime.ts | Initial GET can write history directly | Include initial history loading in the same stale-response boundary |
| apps/web/acceptance/chat-live.mjs | Real browser/API/PostgreSQL test already runs before and after restart | Extend this path for rename durability and preserved messages |

The manual title "Новый чат" is valid. A row lock alone cannot distinguish it from the automatic default, so durable manual intent is required. The owner explicitly approved this additive migration in the implementation directive.

Existing API tests close to the handwritten budget must not grow; separate focused rename test owners reuse their fixtures. Existing shared Accounts, Credits, Jobs, Media, transport and thread pagination remain authoritative.

## Applicable donor comparison

- Donor repository: spikeal8-maker/IZO_ASA.
- Fresh donor main: d1ee3a0ac5114ec08f4a8daee9cf6e41e97d6a7a.
- Bounded paths: phone_chat.py, its owned chat storage update, and services/chat_request_lifecycle.py.
- The donor has PATCH /api/phone/chat/threads/{id} and a persistent owner-scoped thread update. Its current sidebars do not provide the requested rename editor.
- Its blank-title fallback and silent 80-character truncation conflict with the target contract.
- Its first-response title assignment can overwrite a manually selected title.

| Donor item | Classification | Reason |
|---|---|---|
| Explicit persistent owner-scoped PATCH command | ADOPT_BEHAVIOR | Fits existing target Account/Thread ownership |
| Mutation implementation in target transaction and schemas | REIMPLEMENT | Target uses PostgreSQL, shared auth and stricter validation |
| Blank fallback and silent title truncation | REJECT | Target rejects invalid titles and permits 120 Unicode code points |
| First-response overwrite of manual title | REJECT | Violates durable manual naming |
| Donor auth, storage schema, billing and UI component code | REJECT | No duplicate owners or wholesale transfer |

No donor source, user data, credentials or runtime state is copied. The target task defines the interaction and persistence contract sufficiently; no unresolved major product choice requires an external product benchmark.

## Fixed contract

PATCH /api/v1/chat/threads/{thread_id} accepts only a title string and returns the existing ThreadView after the transaction commits.

- Trim surrounding whitespace and accept 1 through 120 Unicode code points.
- Reject empty/whitespace-only values, invalid types, extra fields, NUL and invalid Unicode before PostgreSQL.
- Foreign and missing thread IDs have the same safe not-found response.
- Session, account access, origin and CSRF remain shared backend authorities.
- Rename changes only title, manual intent and the appropriate update timestamp.
- Thread identity, created_at, message order/count, request identities, next sequence and pagination cursors remain unchanged.
- Manual naming must win against automatic naming in either transaction order.
- UI uses server-confirmed data; failures retain the editor draft and the prior saved title.
- Mouse, keyboard and touch all reach the action; cancel/Escape restores focus without unintended drawer closure.
- Updating a title preserves loaded history pages, selected chat, messages and reading position.
- Stale reads and late mutation results cannot overwrite a newer account/session/editor state.

## One-writer assignments

- Backend implementer: Chat route/schema/service/table, forward migration, service/HTTP tests, API README and generated contract.
- Frontend implementer: Sidebar editor and styles, history/runtime wiring, focused Playwright tests, browser restart acceptance and web README.
- Independent reviewer: read-only inspection and verification; fixes return to the implementers.
- Controller: task/scope partition, integration, verification, GitHub publication and evidence; no ordinary product-code authorship.

## Verification record

Targeted service/HTTP, web build, responsive browser and real PostgreSQL/restart evidence are required. SQLite and routed browser tests are not presented as proof of PostgreSQL locking or persisted storage.

### Reviewed source and executed checks

- Final implementation SHA after CI focus follow-up: `7100db48fdffd62555fa9d474148d6467abb86bc`.
- Backend author commits: `0b3435339056d4d0fd0905be46d07cd423c6fd28`, `1b43ac6ea125b125e714c21d59d2fc9e6e2914de`.
- Frontend author commits: `0ab353643dbe751d7cb72dae797ae09fa042a834`, `a5138e15af46732f0e3ea4b7cd21a1d688f4a196`, `6d3a686ad1eb8f4ad5bdd30e09557bbe66075981`, `7c93d241d0b33d73b407642bf946c7e0e4321288`.
- Python 3.13.16: final targeted set **70 passed** in 46.98s: 30 rename domain, 32 rename HTTP and 8 existing thread/history paging and migration tests. The reviewer independently repeated the earlier 64-case version before the final six Unicode regressions were added.
- Full Python suite at backend integration `e5f06bccca218dd70670d2bc25047f9864140ff2`: **1154 passed, 1 skipped** in 225.02s. This predates the final Unicode fix and is not represented as a final-head full-suite run. The skip requires opt-in `IZO_CATALOG_TEST_PG_URL`.
- The TestClient suite required approved execution outside the local sandbox because existing anyio startup stalled there. The repository's no-network fixture was retained.
- Node 24.19.0: npm install and TypeScript/Vite build passed. The normal OpenAPI exporter, `--check` and TypeScript generator passed; generated TypeScript remains ignored by the existing workflow.
- Playwright 1.61.0 / Chromium 149: **45/45 passed** for rename, sidebar and paging across laptop, phone and tablet on frontend `a5138e1`. The final screenshot-only change retained all assertions and its affected scenario passed **3/3** across those projects.
- The reviewer ran **6/6 existing message-copy regressions** on laptop and small phone. An independent stream/load-more/mouse-save browser probe preserved all 52 rows, terminal cursor, focus and scroll (1425 to 1425).
- Independent Unicode parity probe: 900 whitespace-only combinations rejected and 900 combinations around visible text accepted; 120/121-code-point emoji boundary preserved.
- Scope check (23 changed files after the two preauthorized test companions), repository hygiene, documentation, generated contract and whitespace checks passed. Canonical state files, workflows and dependency locks have no candidate diff.

### Independent PostgreSQL evidence

The reviewer authored an independent scheduling/observation probe outside the repository; the controller executed its unchanged source in the disposable `izo-rename-qa-3ea18864` API container on D2-R2. No production credentials, provider calls or existing application volumes were used. A local Compose override assigns subnets only to this new project's networks because the host's default Docker address pools were exhausted; no daemon, VPN, DNS or existing network configuration was changed.

The run passed on PostgreSQL 17.11, READ COMMITTED, migration `0017_chat_manual_title`, on exact implementation SHA `d89eeb4c90b5d444ed121150dbc95c43311437c4`. Backend code is unchanged by the later focus follow-up. The three cases observed real PostgreSQL lock waits rather than inferring locking from SQLite:

| Case | Observed result |
|---|---|
| Rename holds the transaction before first-message admission | Thread/account wait chain observed; manual literal `Новый чат` retained; 2 messages, 1 request, next sequence 3 |
| First admission holds the transaction before rename | Two actual thread locks observed, independent NOWAIT returned 55P03, automatic title was written and then manually replaced; identities and message counts retained |
| Two concurrent renames | Lock chain observed; last serialized title has 120 Unicode code points, manual flag true; no messages or requests created |

Probe SHA256: `24a026ee21f98ea618c021776cfcdc1d3a79ba834221670bcd765021255da51f`.

### Real browser, persistence and final review

On the same exact implementation SHA, real browser requests traversed the built web app, API and PostgreSQL. The isolated fake provider was used. The before phase passed registration, BYOK, SSE, follow-up, rename and concurrent first-message/manual rename. Compose was stopped and recreated with its volumes retained. The after phase passed login, durable manual titles and messages, reload, mobile rename and another reload. Both `CHAT_BROWSER_BEFORE_OK` and `CHAT_BROWSER_AFTER_OK` were emitted; the combined final probe/browser/restart process exited 0 in 61.88s.

The controller inspected the final real 390x844 phone screenshot: the drawer was fully open, both renamed rows were visible and the layout was stable. The reviewer independently inspected the corrected responsive-test phone screenshot.

Independent reviewer `/root/source_audit` issued **APPROVE** for `e195cf9c563a08322c1444672d4355bdc5dab5d5`, then approved the final narrow test-only change at `d89eeb4c90b5d444ed121150dbc95c43311437c4`. Production code was byte-identical between those two revisions. No open code blocker remained. The reviewer did not repair implementation code; findings returned to the authors:

| Finding | Resolution |
|---|---|
| BOM/NEL and mixed-whitespace validation parity | Unified blank detection; added domain/HTTP regressions |
| Editor-close history scroll drift | Restore saved position in layout effect with focus that prevents scrolling |
| Mouse save lost focus when its button became disabled | Accessible pending state plus synchronous duplicate-submit guard |
| Fresh stream refresh dropped loaded history tail | Merge confirmed first-page data while retaining loaded tail and cursor |
| Mobile evidence captured a drawer transition | Wait for settled geometry and disable screenshot animations; assertions retained |

The initial responsive run's 42 passes and 3 scroll failures are retained here as the actual pre-fix result. Two bounded companion test paths were preauthorized; the 32-file cap and all file budgets remain unchanged.

### CI focus follow-up and closure

First published source `90d59ce87e7848d1ab387f5c6630cc94bc2a2d1a`, Foundation CI run `39144072602`, completed SUCCESS: Python **1160 passed, 1 skipped**; Playwright **857 passed, 391 skipped, 3 flaky**. Container and clean offline-preview browser/restart scenarios passed. The controller read the full log and reopened review because all three flaky cases concerned new rename focus behavior; success after the existing retry was not treated as closure.

Two saved-title cases lost focus on tablet/HiDPI; the drawer case sampled focus before its deferred open callback. A one-shot animation-frame callback could run before React committed editor removal and re-enabled the opener. Author fix `7c93d24` replaces that return with a layout effect and consumable intent, respects another connected focused control, clears intent on hide/compact/new edit, and fences late form completion at unmount. Drawer focus also follows the DOM commit. No CI, retries or assertions were weakened; extracted fixture bodies are unchanged.

Natural baseline **48/48 passed**, so it did not reproduce the CI failures locally. A controlled early asynchronous-frame regression failed on the old build in both target projects and passed on the new build; it checks visible saved state and actual focus, not hook calls. Final repeated checks: **80/80 passed without retries** (48 original scenarios, 16 ordering probes, 16 deliberate-focus cases). The affected rename/races/sidebar/paging suite passed **51/51** across laptop/phone/tablet. Build passed.

The reviewer independently verified **15 natural Chromium outcomes** across tablet/laptop/HiDPI: mouse/Enter save, focused search during PATCH, dismiss/reopen/new editor and logout with a late response. Source/bundle hashes matched before and after; the disposable harness's ambiguous login locator was corrected without changing product code. Reviewer verdict: **APPROVE** exact author fix `7c93d241d0b33d73b407642bf946c7e0e4321288`; no open code findings. Final publication, matching trees and fresh exact-head CI results are recorded in PR #269.

Required GitHub workflows must run on the published exact head. Internal subagent review is separate from the repository's required independent GitHub actor or explicit exact-head owner waiver.

Canonical state files remain unchanged by the candidate. Canonical transition and acceptance remain separate checks and must not be inferred from a working UI or a successful candidate CI run.

## Next product direction

Proposed successor: **P1-CONVERSATION-GRAPH-001 — regenerate an answer with durable versions on one active branch**. PRODUCT section 14 and ARCHITECTURE section 10 identify persisted Branch/Turn/AssistantAttempt semantics as remaining P1 work; the current implementation still stores a linear Thread/Request/Message history.

The user-facing increment is "Ответить заново", selection between completed answer versions and durable selection after reload/restart. Introduce the minimum root Branch, ordered Turn and immutable UserMessage/AssistantAttempt relationships, preserving existing identities, names, messages and ownership. Keep the selected answer until a replacement completes; context must include selected completed attempts, not every alternative.

Editing/descendant-branch UI, the full model-aware Context Engine, new retry/provider/billing policies and multimodal expansion are outside that proposed slice. It depends on accepted rename/history behavior and a reviewed migration contract. The registry does not yet activate this proposal; canonical selection follows acceptance. This report does not alter NEXT or create a competing roadmap.
