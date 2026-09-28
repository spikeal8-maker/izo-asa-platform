# Разработка IZO ASA с coding-агентами

Цель: маленькое изменение получает маленький контекст, серьёзное — только необходимый контекст и проверки по риску.
Текущий package/lineage здесь не хранится. Численные бюджеты сопровождаемости принадлежат `MAINTAINABILITY.md`.

## 1. Роли

Владелец задаёт пользовательский результат и принимает дизайн, реальные расходы, merge/release.
Implementer локализует задачу, делает минимальный diff и tests. SELF_REVIEW выполняется тем же агентом после реализации.
Independent reviewer — отдельный проход для high-risk изменений; self-review им не считается.

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

## 7. Общий CI и freeze

После targeted PASS + self-review: `check_docs`, scope-check, generated contracts, diff/secret sanity, затем PR.
Общий CI не заменяется локальными тестами. Skipped stage не является доказательством.

После required workflows current working head замораживается; source/status больше не меняются.
Следующий нормально принятый package запускается только `project_state.py begin-next`, который проверяет
PR/source/workflows/dependencies, создаёт ветку от frozen source и уже там меняет PLAN/CURRENT/CHECKPOINTS.

`project_state.py reconcile-continuation` — отдельный fail-closed transition только для случая, когда active package
нельзя честно принять, но его canonical branch уже продвинулась независимыми verified merges. Он сохраняет historical
package как `superseded_incomplete_reference` с явными acceptance gaps, не создаёт checkpoint и начинает continuation
от текущего canonical HEAD. Это не shortcut для обхода CI, scope, independent review или owner acceptance.

Merge/deploy/live-provider call — отдельные действия.

## 8. Непрерывная сопровождаемость

`MAINTAINABILITY.md` — часть Definition of Done каждого будущего package, а не отдельная разовая уборка.

На каждом package:
1. architecture size guard;
2. headroom regression guard;
3. context route/block budgets;
4. local-doc budget/stale-state guard;
5. scope class/risk;
6. maintainability delta в self-review.

После каждых 5 завершённых product packages проводится полный agent-economy audit. Он ранжирует крупнейшие handwritten
files, самые дорогие routes, локальные docs, map growth, duplicated ownership и tools/workflows у лимитов.
Если долг существенный — создаётся maintenance package; если локальный — закрывается в ближайшем product package.
Лимиты не увеличиваются автоматически.

## 9. Документация

- Изменился локальный элемент → local map меняется только при смене ownership/boundary.
- Новый domain → короткий README + route; ключевые действия → block IDs.
- Новый package → только через state transition.
- Предметный контракт → единственный PRODUCT/ADMIN/UX/ARCHITECTURE/AI_RUNTIME owner.
- Подробный package report → `reviews/<ID>.md`.
- Historical/stale инструкции не остаются рядом с live code.

Перед push обязателен `python tools/check_docs.py`.

## 10. Handoff

Несколько абзацев: package/task, branch/base, diff, tests/CI environment, risks, maintainability delta и один следующий шаг.
Не переносить chain-of-thought, полный чат, огромные логи или repository synopsis.

## 11. Controller / subagent orchestration

Для multi-agent package один **controller** является единственным владельцем package goal, source-audit result, task graph, scope partition, integration order, final SELF_REVIEW и state transition. Controller не передаёт subagent право самостоятельно менять package meaning или repository state.

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

Только controller + repository state workflow меняют `PLAN.json`, `CURRENT.md`, `CHECKPOINTS.json`, active/next package и checkpoint/freeze state. Ordinary subagent state-файлы не меняет.

Если subagents предлагают разные product semantics, controller не выбирает по вкусу: применяется canonical source hierarchy из `MAINTAINABILITY.md`. Если ответа нет — `NEW_DECISION_REQUIRED`.

Review-subagent — READ-ONLY: не исправляет собственный finding и не является implementer того же diff. Internal subagent review не заменяет required structured independent GitHub review или exact-SHA owner waiver.

Controller обязан STOP при `NEW_DECISION_REQUIRED`, unexpected source HEAD change, scope collision, unresolved security/ownership conflict, required CI failure, review blocker, owner-only action или real spend/live operation без отдельного разрешения.
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
