# Разработка IZO ASA с coding-агентами

Цель: маленькое изменение получает маленький контекст, серьёзное — только необходимый контекст и проверки по риску.
Текущий package/lineage здесь не хранится. Численные бюджеты сопровождаемости принадлежат `MAINTAINABILITY.md`.

## 1. Роли

Владелец задаёт пользовательский результат и принимает новые product/security semantics, реальные расходы и owner-only merge/release gates. Владелец **не является обычным QA-исполнителем**: routine code/browser/visual regression должен быть найден агентами до owner preview.
Controller отвечает за decomposition, subagent dispatch, integration, повторные fix/review cycles и доказательство exact candidate. Implementer локализует задачу, делает минимальный diff и tests. SELF_REVIEW выполняется тем же агентом после реализации.
Independent code reviewer не является implementer того же diff. Для user-visible UI отдельный browser/visual reviewer проверяет фактический build. Эти проверки дополняют, а для high-risk не заменяют required GitHub review evidence.

## 2. LOCATE

Старт: `AGENTS.md → CURRENT.md → project_state verify → context.py`.

```sh
python tools/context.py --task "сделай кнопку Скачать шире на телефоне"
python tools/context.py --key web.gallery.download_action
```

При block-locator читать owner вокруг SYMBOL/ANCHOR + local README/test. Если block неизвестен — feature/domain route.
`AMBIGUOUS`/`NOT RESOLVED` означает безопасную остановку и поиск точного текста/symbol/API path.
Не начинать с полного tree/repository scan и не читать broad specs без зависимости.

## 3. SCOPE

До кода фиксируются: `до → после`, package/task, exact base, допустимые пути, non-goals, invariants, ближайший test,
risk и scope class. Классы и file-count budgets заданы в `MAINTAINABILITY.md`.
Sensitive path требует явного approval. Расширение scope сначала объясняется, затем меняется manifest.

## 4. IMPLEMENT → TARGETED TEST

Bug начинается с воспроизводимого failing case; feature — с acceptance case. Изменение минимально связано с задачей,
без соседнего refactor «заодно».

| Риск | Ближайшее доказательство |
|---|---|
| Локальный UI/CSS | build/typecheck + affected E2E/viewports |
| Общий web transport | реально зависимые specs |
| Domain/API | unit + boundary + HTTP/contract |
| Auth/Credits/permissions | negative access + replay/race/idempotency |
| Jobs/Media | owner isolation + retry/restart/storage uncertainty |
| Provider | fake transport + unknown outcome + cancel/recovery + secret/SSRF |
| Migration | upgrade chain + schema + PostgreSQL CI |
| Operations/release | exact artifact + isolated integration + backup/restore/health |

## 5. SELF_REVIEW

После реализации агент прекращает расширять feature и рассматривает собственный diff как reviewer.
Проверяются acceptance, scope, ownership/security/idempotency/retry/cost/privacy, failure/race/restart cases,
contracts/migrations/generated artifacts, local docs/routes и **maintainability delta**.

Maintainability delta обязательно содержит:
- изменённые handwritten files: bytes/lines/headroom;
- initial context bytes затронутых routes/blocks;
- local live-doc bytes;
- scope class/file count;
- факт отсутствия роста near-limit файлов;
- оценку, стала ли следующая похожая правка дороже.

Verdict: `PASS`, `FIX_REQUIRED`, `ESCALATE`.

## 6. Independent review

Обязателен для `risk=high`: auth, permissions, Credits/financial semantics, migrations, paid-provider lifecycle,
credentials/secrets, cross-account access, release/network policy. Такой package не получает checkpoint только на основании
SELF_REVIEW и CI. Требуется отдельное review evidence.

`scope_class=cross_domain`, большой file-count или одновременное изменение API+web **сами по себе не делают package high-risk**. Обычные Chat history/scroll/renderer/actions остаются low/medium, если не затрагивают перечисленные high-risk boundaries. Risk повышается по семантике и trust boundary, а не ради формального review gate.

## 7. Общий CI и freeze

После targeted PASS + self-review: `check_docs`, `repository_hygiene.py`, scope-check, generated contracts, diff/secret sanity, затем PR.
Общий CI не заменяется локальными тестами. Skipped stage не является доказательством.

После required workflows принятый source head замораживается. Отдельный merged closeout PR для `complete` —
единственный допустимый переход к новому HEAD по контракту ниже.
Предвыбранный successor запускается через `project_state.py begin-next`; package с `decides_next=true` и
`next_package=NONE` — через `begin-decided-next`. State workflow создаёт новую ветку и атомарно меняет
PLAN/PACKAGES/CURRENT/CHECKPOINTS. Для terminal `complete` запуск successor не понижает завершённый package.

Для `complete` source HEAD принимается либо ровно по source SHA immutable accepted checkpoint, либо по отдельному
accepted merged closeout PR, указанному через `verified_pr`. Во втором случае head PR должен происходить от
checkpoint source; после введения checkpoint его `complete` status и запись остаются неизменными, а current HEAD
точно совпадает с merge commit PR. Обязательны required PR workflows с проверенным merge tree, совпадающим с деревом
фактического merge commit, успешные required push workflows на exact merged HEAD, а также structured independent
review по exact closeout PR head либо отдельный exact-head owner waiver для этого PR. Waiver исходного checkpoint
не переносится на closeout. При нехватке любого evidence `begin-next`/`begin-decided-next` останавливаются с указанием
отсутствующего или несовпадающего evidence
до создания ветки или записи state.

Если исходный checkpoint впервые вводится в истории более позднего closeout PR, waiver для source PR подтверждается
GitHub-комментарием владельца. Новый structured waiver имеет ровно семь строк ниже: подставляются номер source PR,
exact source SHA, ID обязательных PR runs и конкретная причина.

```text
Owner waiver for source checkpoint PR #<number>: APPROVE
Source HEAD: <40-character SHA>
Independent review: unavailable
Reason: <specific reason>
Foundation CI: <run ID> SUCCESS
Dependency Security: <run ID> SUCCESS
Review Source: <run ID> SUCCESS
```

`Review Source` — историческое имя required workflow, который только фиксирует immutable source snapshot/tree для последующего review evidence. Это **не** code approval и не замена independent reviewer; GitHub UI показывает run-name `Review Source snapshot (not code approval)`.

Для source PR оба времени комментария, `created_at` и `updated_at`, должны быть строго раньше более раннего из
момента первого введения checkpoint и `createdAt` closeout PR. Правка до этого порога допустима; после него waiver
не принимается. Выбранные успешные обязательные PR runs должны завершиться (`updatedAt`) до того же порога, а ID
в комментарии — совпадать с их PR-specific ID. Если используется structured independent review source PR, его
`submitted_at` также должен быть раньше этого порога. Ранее зафиксированный legacy waiver принимается только при
точном совпадении полного тела комментария.

Для отдельного closeout PR выбранные успешные обязательные PR runs должны завершиться (`updatedAt`) строго до
`mergedAt`. Если closeout содержит runtime/product/test/schema/security изменение, его собственное structured independent
review требует `submitted_at < mergedAt`; вместо review допустим отдельный exact-head owner waiver с
`created_at < mergedAt` и `updated_at < mergedAt`. Waiver исходного checkpoint не переносится на такой содержательный closeout.

**Mechanical state-only closeout** — исключение из повторного human-review gate. Он допустим только если machine validator
доказывает одновременно: source product PR уже принят с требуемым exact-head evidence; closeout HEAD происходит от принятого
source/merge; diff ограничен canonical state/checkpoint файлами и их machine-generated evidence; runtime/product/tests/schema/
security не меняются; immutable checkpoint не переписывается; required CI и state/docs/hygiene проверки зелёные. Такой closeout
не получает второй independent code review/owner waiver за тот же product diff: его отдельное доказательство — state validator +
exact-head CI. Merge остаётся owner-only, но owner может одной явной authorization заранее связать product merge и следующий
machine-verified state-only closeout, чтобы controller не прерывал владельца второй раз. Для durable authorization владелец оставляет на source product PR exact comment из трёх строк:

```text
Owner merge authorization for PR #<PR>: APPROVE
Source HEAD: <40-char SHA>
Mechanical closeout merge: AUTHORIZED
```

Comment обязан принадлежать repository owner, быть привязан к exact source SHA и существовать до checkpoint introduction. Его ID сохраняется в checkpoint evidence и повторно аутентифицируется перед использованием. Такая authorization не разрешает содержательный closeout, deploy, live spend или другой PR. Любое отклонение от state-only allowlist
немедленно возвращает обычный closeout review/waiver contract.

Единственное историческое исключение, закреплённое в `legacy_pr252_review`, принимает owner-authenticated pre-merge
comment как legacy closeout evidence лишь для зашитых в этом helper точных PR, head, merge commit и comment ID.
Проверяются принадлежность комментария владельцу, время до merge, его неизменённое содержание с exact head, `APPROVE`
и ID успешных обязательных CI runs, соответствие merge commit PR и canonical main lineage. Это не structured GitHub
approval и не новый owner waiver. Для всех остальных closeout PR действует только предшествующий merge structured
independent `APPROVED` review либо отдельный exact-head owner waiver.

Lifecycle status contract: `active` — текущая работа; `planned_next` — явно выбранный successor;
`technical_pass` — technical acceptance, merge/deploy не подразумеваются; `complete` — terminal и immutable;
`planned` — не начат; historical/superseded statuses не становятся автоматически continuation base.

`project_state.py reconcile-continuation` — отдельный fail-closed transition только для случая, когда active package
нельзя честно принять, но его canonical branch уже продвинулась независимыми verified merges. Он сохраняет historical
package как `superseded_incomplete_reference` с явными acceptance gaps, не создаёт checkpoint и начинает continuation
от текущего canonical HEAD. Это не shortcut для обхода CI, scope, independent review или owner acceptance.

Merge/deploy/live-provider call — отдельные действия.

## 8. Непрерывная сопровождаемость

`MAINTAINABILITY.md` — часть Definition of Done каждого package и единственный owner structural cadence,
threshold triggers и audit finding classes. Этот документ не создаёт второй календарь cleanup.

Controller обеспечивает Maintenance Delta и required gates текущего package, но COSMETIC/LOCAL_DEBT/
STRUCTURAL_BLOCKER обрабатываются строго по `MAINTAINABILITY §7`. Hard limits не повышаются ради PASS.

## 9. Документация

- Изменился локальный элемент → local map меняется только при смене ownership/boundary.
- Новый domain → короткий README + route; ключевые действия → block IDs.
- Новый package → только через state transition.
- Предметный контракт → единственный PRODUCT/ADMIN/UX/ARCHITECTURE/AI_RUNTIME owner.
- Подробный package report → `reviews/<ID>.md`.
- Historical/stale инструкции не остаются рядом с live code.

Перед push обязателен `python tools/check_docs.py`.

## 10. Handoff

Внутренний handoff между агентами: package/task, branch/base, diff, tests/CI environment, risks, maintainability delta и один следующий шаг.
Не переносить chain-of-thought, полный чат, огромные логи или repository synopsis.

Owner-facing status короче внутреннего handoff и не перекладывает QA на владельца. Формат: `ЭТАП`, `ЧТО ГОТОВО`,
`ЧТО СЕЙЧАС ДЕЛАЮТ БОТЫ`, `QUALITY (code/browser/visual/CI)`, `ЧТО УВИЖУ`, `НУЖЕН ЛИ ВЛАДЕЛЕЦ`.
Если owner action не нужен, controller продолжает работу; status не является STOP-событием.

## 11. Controller / subagent orchestration

Для multi-agent package один **controller** является единственным владельцем package goal, source-audit result, task graph, scope partition, integration order, final SELF_REVIEW и state transition. Controller не передаёт subagent право самостоятельно менять package meaning или repository state.

### CONTROLLER_ONLY_ORCHESTRATION

Если task явно задан как `controller + subagents`, controller по умолчанию **не является ordinary implementation writer** для product/runtime кода. Он восстанавливает state, выполняет SOURCE_AUDIT, строит task graph, делит scope, dispatches writing/review tasks, проверяет diff/SHA/tests, интегрирует принятые isolated results, принимает/отклоняет/reassigns работу, проводит package-level gates, state transitions и выбирает следующий bounded task.

Обычная product/runtime implementation по умолчанию делегируется implementation subagent. Если после integration нужна содержательная code correction, controller назначает fix/integration subagent вместо превращения себя в основного implementer.

Controller может самостоятельно выполнять orchestration/integration mechanics без новой product semantics: inspect/compare/assign, интегрировать или cherry-pick уже принятый isolated result когда это разрешено repository governance, запускать checks, проверять evidence и вызывать state workflow. Это правило само по себе не разрешает PR merge/deploy/owner-only action.

Исключение: если multi-agent mode объективно не применяется и package явно single-agent/local, обычный workflow из предыдущих разделов допустим; искусственно создавать subagent для каждой CSS-строки не требуется. Но при явном `controller + subagents` controller-only orchestration обязательно.

Каждый writing subagent до старта получает явный contract:

```text
TASK_ID
PACKAGE_ID
BASE_SHA
GOAL
READ_SCOPE
WRITE_SCOPE
DEPENDENCIES
INVARIANTS
NON_GOALS
ACCEPTANCE
TARGETED_TESTS
HANDOFF_FORMAT
STOP_CONDITION
```

Writing task без этого contract не стартует.
### Parallelism и isolation

Главное правило: **one path = one active writer**. Параллельная реализация разрешена только для disjoint write scopes. Если два subagent требуют один owner/path, controller сериализует работу либо repartitions scope; competing concurrent writes запрещены.

Параллельные writing subagents используют separate branch/worktree или другую доказанную isolated patch boundary. Два write-agents не работают одновременно в одном mutable file set. Controller интегрирует результаты в package branch и повторно проверяет diff/tests после integration.

Subagent не расширяет scope самостоятельно. Нужен новый path/domain → вернуть `NEED_SCOPE_EXPANSION`; controller повторяет source/ownership/scope analysis и только затем выдаёт изменённый assignment.
### State, conflicts и reviewer

Только controller + repository state workflow меняют `PLAN.json`, `PACKAGES.json`, `CURRENT.md`, `CHECKPOINTS.json`, active/next package и checkpoint/freeze state. Ordinary subagent state-файлы не меняет.

Если subagents предлагают разные product semantics, controller не выбирает по вкусу: применяется canonical source hierarchy из `MAINTAINABILITY.md`. Если ответа нет — `NEW_DECISION_REQUIRED`.

Review-subagent — READ-ONLY: не исправляет собственный finding и не является implementer того же diff. Internal subagent review не заменяет required structured independent GitHub review или exact-SHA owner waiver.

При required CI failure или review blocker controller останавливает **приёмку текущего candidate**, freeze и зависимые шаги, но не перекладывает обычное исправление на владельца. Если причина — воспроизводимый дефект внутри уже разрешённого package/task scope, controller обязан назначить bounded fix-subagent, затем новый read-only review и проверки. После исправления требуются полный required CI и повторный required review для нового exact source HEAD; бесконечные reruns и обход gates запрещены.

Для user-visible package до owner preview применяется delegated quality loop:

```text
IMPLEMENTER(S)
→ integration
→ SELF_REVIEW
→ independent code reviewer
→ browser/visual reviewer
→ targeted tests
→ required CI
→ fresh GitHub review when configured
→ finding ? FIX-SUBAGENT → re-review/retest : freeze candidate
```

Browser/visual reviewer работает на фактическом exact build, а не на описании implementer. Минимум: desktop+phone, light+dark,
long/empty/error state по применимости, console errors, видимый текст/labels, computed contrast/color для критичного prose,
overflow/geometry, build/source provenance. Он не обновляет screenshot baseline только ради сокрытия regression.

Полный STOP до отдельного разрешения обязателен только при `NEW_DECISION_REQUIRED`, unexpected source HEAD change,
реальном scope collision/expansion за пределы уже разрешённого package, unresolved security/ownership conflict, owner-only
merge/deploy/release action, real spend/live operation или прямом запрете в task contract. Обычный bug, CSS/visual regression,
review finding, focused test failure и scope-preserving fix — внутренний bot-to-bot цикл, а не owner interruption.

### Owner preview cadence и delegated development

Внутренние quality gates выполняются для каждого package, но owner preview — **product milestone, а не ручной gate каждого технического slice**. Controller показывает владельцу результат после meaningful visible UX milestone (обычно группа связанных bounded slices) либо когда требуется реальное product decision. До показа обязательны code review PASS, browser/visual review PASS, required CI PASS и exact source/build provenance.

Владелец оценивает продукт через несколько простых сценариев, а не проверяет SHA, DOM, console, race или CSS за агентов. Если reviewer может доказать проблему автоматически, она должна быть найдена до owner preview.

Для заранее разрешённого non-sensitive P1 work controller продолжает package→package без status-stop. Новый owner interrupt требуется только по STOP-условиям выше. Это не отменяет owner-only merge/release policy: разрешения можно **коалесцировать** в один понятный gate, но нельзя выдумывать их задним числом.

### Subagent handoff

Минимальный handoff:

```text
TASK_ID
BASE_SHA
RESULT_SHA / patch identity
CHANGED_PATHS
TESTS
RESULT
RISKS
BLOCKERS
```

Controller не принимает «готово» без exact diff/evidence. Handoff-critical результат materialize через GitHub-first process до STOP.

## 12. Bounded ChatGPT + Claude benchmark procedure

Требование о том, **когда** benchmark обязателен, принадлежит `MAINTAINABILITY.md`. Здесь находится только execution procedure.

Для существенного user-visible Chat behavior, которое source audit признал не полностью определённым IZO ASA contracts, implementer перед `NEW_DECISION_REQUIRED` исследует **оба current ChatGPT и current Claude**. Используются current official product/help docs или проверяемая current product surface; старые воспоминания не evidence.
Benchmark record фиксирует:

```text
BENCHMARK_DATE
CHATGPT_SOURCE
CLAUDE_SOURCE
BEHAVIOR_UNDER_DECISION
APPLICABLE_CRITERIA
CHATGPT_OBSERVATION
CLAUDE_OBSERVATION
IZO_TARGET_CONSTRAINTS
DECISION
REASON
```

По применимости сравниваются interaction flow, discoverability, editing, regenerate/retry, branch/history behavior, attachments/files/tools/artifacts, copy/export, streaming, error/recovery, mobile/desktop, accessibility, latency/perceived responsiveness и privacy/safety.

Нельзя выводить «ChatGPT делает X → копируем X» или «Claude делает Y → копируем Y». Решение сопоставляет current IZO contract + existing target implementation + applicable donor + оба benchmarks и выбирает best fit для IZO ASA; допускается совместить сильные стороны обоих, если итоговая semantics непротиворечива. После owner/contract decision external products перестают быть live dependency: authority — записанный IZO ASA canonical contract.
