# P1-CHAT-MESSAGE-EDIT-001 — implementation and review evidence

## Scope and activation

The owner selected Edit-as-new-branch after accepted Conversation Graph closeout PR #274. Existing Chat/Graph is the implementation owner; no parallel backend or Graph rewrite is authorized. One finite cross-domain high-risk manifest reserves backend 19, frontend 15 and controller/workflow 6 paths, max 40. Initial ARCH/UX integration is serialized before product writer dispatch. Independent review and actual desktop/mobile browser QA are required.

PR #274 source `c5b884803dbbd6e88198f2960f9c11e89c4897ab` was ordinarily merged into protected main as `a0e58dfd0d3daf3dbc027c94eb857fd9c8724c4e` after exact owner waiver comment 6272751653. Fresh push Foundation 39293141960 and Dependency 39293141940 succeeded on the actual merge; these are predecessor acceptance evidence, not Edit test results.

The unmodified `project_state.py --github-transport connector-stdio begin-decided-next --verified-pr 274` genuinely activated this package through 83 live correlated requests, exit 0. Invocation: 2026-10-19T17:42:45.354Z to 17:45:23.819Z. Activation commit: `c3e295a56d9e1fbba54c5942786f7fb4245ab5c8`. The command writes only PLAN/PACKAGES/CURRENT; all 29 checkpoints remain byte-identical, SHA256 `f7417811b75836e0c9fa86f8dc1260db5a8a5c925c3307ca4da31c668275de31`. All 65 prior package records remain unchanged, Graph terminal complete. Live transcript SHA256 `0a355ee5496a5285258aaf4e808a5230f1da947b2ec8e10239501fedf8209357` (8218173B) is retained in controller evidence.

## SOURCE_AUDIT and decisions

Continue the prepared task graph against exact accepted Graph sources. The bounded architecture/UX clauses D1–D6 are canonical; the following DTO/normalization details coordinate the two disjoint writers. Source-level design review found no blocking gap, but is not approval of unimplemented code or tests. Preserve existing GraphPage.unknown_request_id as a thread-wide server query/field after branch switching and full reload. Inherited-prefix manual selection uses active-branch membership; completion retains the real execution-branch guard.

## API and interaction contract


Все пути имеют prefix `/api/v1/chat/threads/{thread_id}`. Имена и envelope ниже взяты из согласованных prep/readiness. Session, ownership и существующий transport остаются общими; mutation требует действующий origin/CSRF. Caller не назначает owner, private asset facts, credentials или provider endpoint. `RequestView`, `MessageView.request_id` и существующий SSE lifecycle сохраняются.

| Команда | Request | Успех и response | Условия |
| --- | --- | --- | --- |
| `POST /turns/{source_turn_id}/edit` | `{request_id: UUID, branch_id: UUID, source_attempt_id: UUID, expected_revision: int>=0, text: string}` | `202 {thread_id, created_branch: BranchView, turn_id, request: RequestView, active_branch_id, revision}` | `branch_id` — наблюдаемая active source branch. `source_attempt_id` — selected либо latest terminal branch-visible attempt при selection NONE. `turn_id` в receipt — новый edited turn. Не принимает выбор другой модели или `attachment_ids`. |
| `GET /branches` | Optional `before_branch_ordinal: positive int64`, exclusive | `200 {thread_id, active_branch_id, active_branch: BranchView, revision, branches: BranchView[<=50], next_before_branch_ordinal: int64|null}` | Текущая active branch включена отдельным объектом даже вне страницы. Cursor продолжает список веток; UI label — «Ветка N». |
| `PATCH /branch-selection` | `{branch_id: UUID, target_branch_id: UUID, expected_revision: int>=0}` | `200` существующий coherent `GraphPage` новой active branch | Target принадлежит тому же Thread и проверяется до CAS. После общих guards выбор уже активной target с актуальным CAS — no-op. Не создаёт request или execution. |
| `POST /requests` | Существующий `RequestCreate` плюс optional all-or-none `{branch_id: UUID, expected_revision: int>=0}` | `202` неизменённый `RequestView` | Новый UI всегда передаёт пару. Новый unfenced запрос совместим только с root-only Thread; при наличии descendant → `409 branch_selection_required`. Маршрут обычной отправки сохраняется. |
| `GET /graph` | Существующий exclusive `before_turn_sequence`; optional expected `branch_id` | `200` существующий `GraphPage`, ≤50 turns | Initial read может открыть текущую active branch; continuation использует её branch fence. Visibility и selection определяются membership этой ветки. |
| `GET /turns/{turn_id}/attempts` | Существующий exclusive `before_ordinal`; optional expected `branch_id` | `200` существующая attempt page, ≤20 attempts | Глобальные ordinals не перенумеровываются; position/count/neighbors вычисляются по доступным ветке attempts. |

`BranchView = {id: UUID, parent_branch_id: UUID|null, fork_from_turn_id: UUID|null, branch_ordinal: positive int64, created_at: timestamp}`. Root сохраняет `id=thread_id`, ordinal 1 и null ancestry. Child получает следующий per-Thread ordinal под Thread lock. `fork_source_attempt_id` остаётся внутренней provenance; BranchView его не добавляет. Переименование/архивирование ветки в этот срез не входят.

### Модель, вложения, lifecycle и повтор

Сервер подтверждает source membership и выбранную/latest terminal попытку, берёт её public model и выполняет текущие capability, authorization, credential generation, asset readiness/ownership и vision проверки через действующий admission. Исходные ordered asset IDs повторно используются для новых snapshot rows нового user/request; прежние rows и original message неизменны. Файлы не перезагружаются. При ошибке новый fork/admission не фиксируется.

Одна финальная транзакция создаёт request, child, prefix memberships/selection, новый user/assistant/turn/attempt, фиксирует selected-prefix context и active branch/revision. Edited turn начинает с NONE; существующий durable COMPLETED selection owner выбирает успешную попытку. Snapshot исключает прежний fork turn, его ответ, suffix и невыбранные варианты. Существующие Thread→Request lock order, stop/reconciliation и paid-marker правила не меняются.

После обычной проверки body и ownership принятый точный UUID проверяется **до** fresh source/CAS/D5 и dynamic readmission. Material identity связывает kind, source branch/turn/attempt, нормализованный текст и сохранённый asset intent; `expected_revision` является precondition нового запроса. Replay возвращает прежние `created_branch/turn_id/request` вместе с **текущими** `active_branch_id/revision`, не переключает branch и не вызывает provider. Новый material/kind под принятым UUID — conflict. Клиент сохраняет pending UUID/material intent; отложенный receipt не заменяет более свежий выбор ветки.

### Compatible regeneration receipt after a branch change

WIP review identified an existing-regeneration edge introduced by branching: an accepted request may belong to a turn excluded from the currently active child, or to an inherited turn with a different branch-local selection. Returning an empty/current-branch projection of that old turn is incoherent. Rejecting an exact accepted UUID with a fresh CAS error would weaken D6; nullable turn or false active branch would change the existing contract.

The bounded additive clarification keeps `GraphRequestAccepted.request/turn` and adds `execution_branch_id`, read from the accepted `chat_assistant_attempts.branch_id`, never from the turn's immutable origin. Under the same Thread lock, `turn` is projected through that execution branch membership/selection while `active_branch_id/revision` remain the actual current state. Exact accepted replay remains 202 without readmission, reactivation or a new execution. Same-branch behavior remains compatible.

The client validates request ID, Thread, original turn and execution branch against the frozen intent. It merges the returned turn only when intent/execution/observed/current branches match and the whole loaded-range revision remains coherent. Otherwise it confirms the recorded identity and recovers a coherent current Graph; terminal requests never start SSE again. A missing additive field in old same-branch fixtures is accepted only with matching intent/current active branches. A one-turn receipt cannot validate stale cached ranges merely because it has a newer revision.

Independent design review accepted this implementation clarification with mandatory regressions: excluded root turn after Edit; inherited root-origin turn regenerated inside a child and replayed after switching; same-branch replay; delayed receipt after branch or revision changes. It changes no user-facing D1-D6 semantics and remains inside the existing API/frontend scopes. Actual code/test approval is still required.

### Ошибки и precedence

| HTTP | Контракт |
| --- | --- |
| `401` | Нет действующей authenticated session. |
| `403` | Origin/CSRF failure. |
| `404` | Missing/foreign Thread, source turn, branch, attempt или request identity; чужая принадлежность не раскрывается через CAS. |
| `409 graph_revision_conflict` | Fresh branch/revision/source precondition устарело; перед новым execution требуется coherent read. |
| `409 branch_selection_required` | Fresh ordinary send в branched Thread без branch/revision пары. |
| `409 request_conflict` | Уже принятый UUID с другим material intent или видом операции. |
| `409 active_request_exists` | Pending/streaming запрещает Edit и active-branch mutation; автоматического abort/stop нет. |
| `409 provider_outcome_unknown` | UNKNOWN запрещает новое execution во всём Thread. Metadata-only выбор ветки сохраняет global marker и не выполняет admission/provider. |
| `422 message_unchanged` | Fresh valid Edit совпадает с original после N; UUID не резервируется, branch/request/context/provider и rate slot отсутствуют. |
| `422` | Существующие type/raw length/NUL/content, invalid model/vision проверки. |
| `413` | Существующие body/context bounds. Остальные действующие admission/rate ошибки сохраняются. |

Для D5 порядок: существующая body validation → authentication/CSRF/ownership → owned exact accepted replay → fresh membership и CAS → normalized no-change → обычные changed-request admission guards с финальной locked revalidation. No-change располагается до нового admission, rate slot и его ancillary expiry path; ordinary send/regenerate expiry behavior не переставляется. Две новые no-change команды не создают данные и не расходуют rate slot. Ошибка не является `202` no-op и не маскируется под accepted replay.

### N(text), raw bound и controlled textarea

N — текущий Python `str.strip()`. Boundary set: U+0009–000D, U+001C–001F, U+0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028, U+2029, U+202F, U+205F, U+3000: 29 code points. BOM U+FEFF и U+200B сохраняются. Внутренние пробелы/CRLF, регистр и NFC/NFD не нормализуются. Raw max 6000 code points применяется до strip, затем NUL rejection; пустой N допустим только с сохранёнными attachments. JS `trim()`, `\s`, `.length` и textarea `maxlength` не воспроизводят весь контракт.

Точный helper остаётся в `ChatMessageEdit.tsx`. Original persisted text хранится отдельно; opening/mount/focus/blur не заменяют draft нормализованным DOM value. Untouched CRLF оставляет Save disabled. Только actual input изменяет candidate; реальный LF/CRLF comparison следует N. UI сначала учитывает raw validity, потом unchanged reason; disabled путь не создаёт network admission или durable pending UUID. Сохраняются все 22 D5 cases из backend readiness, включая NEL/C0/BOM/ZWSP/NUL, 6000/6001 before-strip, supplementary Unicode, attachments, replay и concurrent unchanged.

### Страницы, selected context, фокус и races

Owned coherent page читается под существующим Thread lock. Переданный branch fence обязан принадлежать Thread и совпадать с active branch; курсор другой ветки не применяется. Prefix membership копирует существующие immutable turn/attempt IDs и их branch-local selection; последующие варианты parent/sibling не входят в child автоматически. Legacy `before_sequence`, physical sequence и message/request IDs сохраняются.

Новый branch hook удерживает кеши веток. При возвращении согласуются **все** ранее загруженные диапазоны Graph/attempt selection на одной branch/revision; обновления последних 50 недостаточно. Mixed/stale revision блокирует execution до coherent reload; серверный CAS остаётся финальной границей. Успех CAS с последующей ошибкой GET не означает rollback: UI удерживает loading/error lock и даёт повторить чтение. Account/Thread/branch/epoch/selection version фильтруют запоздавшие HTTP, SSE и async cleanup. UNKNOWN marker сохраняется даже при просмотре другого metadata-selected branch.

FE15 использует постоянную композицию user `ChatMessageEdit` с исходным `message.id` и неизменным первым child `ChatMessage`; assistant keys остаются прежними. Source turn ищется по `turn.user_message.id`. Новый wrapper не дублирует message/turn anchors. В ChatPage остаются native selector, props wiring и bounded layout bridge для существующего `useChatScroll`; composerVersion не сбрасывается, используется `openThread(threadId,threadId)`. Отмена возвращает фокус живому trigger, accepted suffix change — существующему элементу. Фактический layout-effect порядок, scroll, Copy/attachments и desktop/mobile поведение подтверждаются после реализации.

## Writing tasks and gates

Each writer receives all 13 DEVELOPMENT contract fields and the exact integrated canonical base. Backend owns the 19 API/migration/contracts/tests paths; frontend the 15 UI/UX/browser acceptance paths. Reviewer changes none of the reviewed code. Controller integrates accepted commits and returns substantive defects to writers. All file and owner-size limits remain unchanged. New local README content replaces routing clauses within the existing 6000 B domain cap.

Required tests include ownership/auth/CSRF, original-history/attachment retention, branch-local context and selection, exact UUID replay/material conflicts, PostgreSQL contention/rollback/migration, 22-case D5 normalization, coherent cached pagination, stale HTTP/SSE and UNKNOWN A→B→reload. Desktop/mobile QA covers edit/save/cancel/loading/error, focus/scroll/composer preservation and both real fake-provider retained-volume restart phases.

### Bounded backend owner redistribution before the final race tests

Independent review required two additional real PostgreSQL overlaps: Edit against manual answer selection, and branch selection against actual gated completion. Four test owners on `452b437a4c925824e4bea258dbd85ca42bf528a6` had only 160 B combined growth room; moving tests among them would not provide the required coverage within the existing limits. The controller therefore reviewed a responsibility split before authorizing further writes.

The accepted-request receipt belongs in `graph_requests.py`; the selected-turn projection belongs in `graph_selection.py`, alongside attempt projection. Physical and Graph page reads remain in `history_pages.py`. This retires the provisional, never-published `graph_projection.py` module while preserving every function and the existing public history-page imports. Reverse imports are local to prevent module-load cycles. The single freed final-diff path becomes `tests/test_chat_branches_postgres.py`, which owns the existing nine Branch PostgreSQL cases plus the two additional overlaps. The old Graph runner remains the required entry point. No runtime condition, assertion, workflow, size limit or scope-count limit is removed.

The pre-write placement record has SHA256 `31e619bb24f86113f8ea2515330ea79e25556e0cc6472e08cfa33eed2b6af290`. Measured candidate sizes: history pages 9553 B / 158 lines, selection 8808 B / 189, requests 9010 B / 167, branch migration tests 9685 B / 188 and PostgreSQL branch tests 7955 B / 140. The 47 B remaining growth room in history pages is a constraint on its next expansion. These are candidate measurements; acceptance still requires the applied exact diff, fresh tests and independent review.

The final manifest remains nineteen backend, fifteen frontend and six controller/workflow paths, maximum forty changed paths against the unchanged accepted base. Earlier implementation commits and the explicit relocation/deletion commit remain in the published ancestry. Publication validates each historical commit against the manifest recorded for its stage, with previously authorized deletion checked through its parent history; the final diff is checked independently by the unmodified scope guard. This records the module retirement without concealing a file or discarding implementation history.

### Existing UI styles and the Graph regression contract

The frontend reuses the existing theme, message-action and form styles, with bounded layout props for the editor and wrapping toolbar. Its provisional `ChatRenderer.css` changes are removed byte for byte. An explicit object containing only the eight existing Sidebar props replaces repetitive UI wiring; it does not spread arbitrary runtime fields into the component. The measured candidate keeps ChatPage at 9577 B, runtime at 9564 B and editor at 9565 B. Eighteen targeted desktop/phone checks, including UNKNOWN, failed-read recovery, deliberate external focus and both-theme reading anchors, passed before this scope replacement; the complete frozen frontend remains to be validated.

The unchanged fifteen-path frontend allocation replaces `ChatRenderer.css` with the existing `conversation-graph.spec.ts`. Its historical `olderReads === 1` assumption conflicts with D6's required coherent reread. The revised regression must retain all 53 rows, stable DOM order and the less-than-4-pixel reading anchor, and explicitly verify a fresh older-range response containing the current revision and selected answer. Changing only a request counter or relaxing the data/scroll assertions is insufficient. All new Edit UI and race cases remain, including the independently reproduced concurrent older-load/head-reload loss. This changes the obsolete network expectation while strengthening the approved data-coherence contract; no test skip or limit increase is authorized.

## Implementation status at contract integration

Product implementation: NOT YET IN THIS COMMIT. Edit targeted tests, integration tests, independent code review, browser QA and own full PR CI: NOT RUN. Predecessor CI is not credited as Edit execution. Record actual results as implementation is integrated; no future PR merge, production deployment or paid provider call is authorized by this package dispatch.
