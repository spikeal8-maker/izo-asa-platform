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
Следующий package запускается только `project_state.py begin-next`, который проверяет PR/source/workflows/dependencies,
создаёт ветку от frozen source и уже там меняет PLAN/CURRENT/CHECKPOINTS.

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
