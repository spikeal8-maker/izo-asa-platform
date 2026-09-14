# IZO ASA · обязательные правила coding-агента

Цель: безопасная правка должна требовать минимального достаточного контекста. Текущая ветка/пакет/следующий шаг
живут только в `docs/CURRENT.md` и `docs/PLAN.json`.

## Старт

1. Прочитать `docs/CURRENT.md`; выполнить `python tools/project_state.py verify`.
2. Запустить `python tools/context.py --task "<задача>"` или выбрать точный `--key`.
3. При `CONTEXT BLOCK` читать owner только вокруг SYMBOL/ANCHOR. Не открывать файл целиком заранее.
4. `AMBIGUOUS`/`NOT RESOLVED` → искать точный visible text/symbol/API path, не угадывать.
5. До кода зафиксировать `до → после`, package/task, base, finite scope, non-goals, риск и ближайший test.

## Неподвижные границы

- Account / Credits / Jobs / Media общие для providers и клиентов; второй ledger/auth/gallery запрещён.
- Browser не владеет identity, permissions, price, provider key/config, object key, attempt/fence.
- Ownership/permissions проверяет backend.
- Unknown paid outcome сначала reconcile; blind retry запрещён.
- Реальные ключи/расходы, платежи, почта, боты, DNS, merge/deploy/release требуют отдельного разрешения.
- Unit/UI не используют production сеть/секреты; integration работает на изолированных DB/S3.

## Экономный цикл

`LOCATE → SCOPE → failing/acceptance case → minimal IMPLEMENT → TARGETED TEST → SELF_REVIEW → full CI → FREEZE`.

Не ослаблять tests/limits и не расширять scope ради PASS.

Файлы, context routes, local docs и scope обязаны соблюдать `docs/MAINTAINABILITY.md`.
Near-limit файл не увеличивается дальше без split. Limit нельзя повышать автоматически после failure.

## SELF_REVIEW

После реализации агент прекращает добавлять функции и проверяет:
- решена ли исходная задача;
- каждый ли изменённый файл нужен;
- нет ли ownership/security/idempotency/retry/cost/privacy regression;
- покрыты ли error/race/refresh/restart cases по риску;
- не ослаблена ли проверка ради PASS;
- не выросла ли стоимость следующей агентской правки;
- корректны ли local README/block/route/test.

Verdict: `PASS`, `FIX_REQUIRED`, `ESCALATE`. High-risk области требуют отдельного independent review по
`docs/MAINTAINABILITY.md`.

## Scope, CI и freeze

Machine scope конечен. Нельзя `reset --hard`, force-push, чистить чужой WIP, auto-merge или auto-deploy.
Перед push: docs/scope/generated/diff/secret sanity и профильные tests. Полный CI перед технической приёмкой не урезается.

После успешных required workflows current working head замораживается. PR workflow evidence называется
`pr_merge_tree`, если checkout был synthetic merge. Следующий package запускается только через
`tools/project_state.py begin-next`, который проверяет source head, dependencies и CI evidence и создаёт новую ветку.

Статусы IMPLEMENTED / SELF_REVIEWED / TESTED / PUSHED / INDEPENDENTLY_REVIEWED / MERGED / DEPLOYED /
OPERATIONALLY_VERIFIED не склеиваются словом «готово».

## Документация и handoff

`docs/DOCS_SYSTEM.md` определяет владельца фактов. Новый MASTER_PLAN/NOW/ROADMAP запрещён.
History/reviews/checkpoints не являются default context.

Handoff: package, branch/base, фактический diff, проверки, открытые риски и один следующий шаг.
Не переносить весь чат, reasoning или большие логи.
