# IZO ASA · обязательные правила coding-агента

Цель: безопасная правка должна требовать минимального достаточного контекста. Этот файл содержит
только долговечные правила. Текущая ветка/пакет/следующий шаг находятся в `docs/CURRENT.md` и
`docs/PLAN.json`; не записывать mutable project state сюда.

## 1. Старт любого задания

1. Прочитать `docs/CURRENT.md` и выполнить `python tools/project_state.py verify`.
2. Выполнить `python tools/context.py --task "<запрос пользователя>"` либо выбрать точный block/route через `--key`.
3. Если найден `CONTEXT BLOCK`, искать только указанный OWNER/SYMBOL/ANCHOR и читать окружающий блок; весь файл заранее не читать.
4. Если router вернул `AMBIGUOUS`/`NOT RESOLVED`, искать точный visible text/symbol/API path, а не выбирать направление наугад.
5. Зафиксировать ожидаемое `до → после`, non-goals, `current_package_base`/working branch, scope и профильную проверку.
6. Если запрос ведёт в parallel/superseded lineage — остановить feature work и разрулить lineage.

Расширять чтение можно только из-за конкретной недостающей зависимости. После двух одинаковых неудач
не повторять широкий поиск: сформулировать новую диагностическую гипотезу.

## 2. Неизменяемые границы продукта

- Account / Credits / Jobs / Media общие для всех providers и клиентов; не создавать второй ledger/auth/gallery.
- Browser не владеет identity, ценой, provider key, connection, executor, object key, attempt или fence.
- Ownership/permissions проверяет backend. Известный URL не делает private asset публичным.
- API/local/provider pools разделяются по контракту; unknown paid outcome сначала reconcile, не blind retry.
- Local→paid, реальные ключи, платежи, почта, боты, DNS, production release требуют отдельного разрешения.
- Unit/UI не используют production сеть/секреты. Integration работает на изолированных DB/S3.
- Coding-agent и пользовательский AI — разные trust domains; продуктовый AI не получает GitHub/shell/Docker права.
## 3. Экономный цикл изменения

Сначала failing/acceptance case, затем минимальное связное изменение, затем ближайший test. Полный suite
не запускается после каждой строки, но общий CI перед технической приёмкой не урезается.

Не переустанавливать зависимости без нового checkout/изменённого lock/runtime. Не обновлять библиотеки
ради локальной UI-правки. Не менять tests/snapshots/limits, чтобы скрыть дефект. Общий contract, migration,
CI, LICENSE, secret/network/release policy являются чувствительными областями и требуют явного scope.

Machine scope конечен. Если он стал недостаточен, сначала объяснить новую зависимость; не повышать лимит
автоматически. Один пишущий агент на пересекающиеся файлы. Не reset --hard, force-push, cleanup чужого WIP,
auto-merge или auto-deploy.

**Frozen checkpoint:** после успешного требуемого CI current working head больше не редактируется. Для PR CI
доказательство называется `pr_merge_tree`, а не exact-source execution. Следующий package запускается только
`tools/project_state.py begin-next`: команда сама связывает PR/workflows с source head, создаёт новую ветку от
этого head и меняет state уже в новой ветке.

## 4. Обязательный SELF_REVIEW

После законченного атомарного изменения агент **перестаёт добавлять функции** и выполняет отдельный проход:

- выполнено ли исходное acceptance, а не соседняя задача;
- какой фактический diff и нет ли изменений вне scope;
- нарушены ли ownership/security/idempotency/retry/cost/privacy invariants;
- какие реальные failure/race/refresh/restart случаи не покрыты;
- не стал ли тест зелёным из-за ослабления проверки;
- соответствует ли локальная документация фактическому коду;
- verdict: `PASS`, `FIX_REQUIRED` или `ESCALATE`.

`FIX_REQUIRED` означает исправить найденное и повторить SELF_REVIEW. Это самопроверка, не независимый review.
Шаблон: `docs/templates/SELF_REVIEW.md`. Высокорисковые auth/credits/permissions/migrations/provider-cost/
secrets/release изменения требуют отдельного review-прохода после self-review.
## 5. Публикация и отчёт

Перед push: `python tools/check_docs.py`, scope-check, профильные tests, diff/secret sanity и необходимые
generated contracts. CI evidence обязан быть связан с source head. PR workflow проверяет synthetic merge tree и так и называется; exact-source execution заявляется только когда workflow действительно checkout-ил source commit.

Статусы независимы: IMPLEMENTED / SELF_REVIEWED / TESTED / PUSHED / INDEPENDENTLY_REVIEWED / MERGED /
DEPLOYED / OPERATIONALLY_VERIFIED. Не склеивать их словом «готово».

Handoff содержит: branch/base, package ID, изменённое поведение, scope, выполненные проверки/ошибки,
неизвестные риски и **один** следующий шаг. Не переносить всю историю чата.

## 6. Документация

`docs/DOCS_SYSTEM.md` определяет владельца каждого типа факта. `INDEX.md` — стабильная карта, не roadmap.
`PLAN.json` — единственный machine-readable план. `STATUS.md` — доказанные факты. `reviews/` и `history/`
не являются входом обычной задачи. Новый MASTER_PLAN/NOW/ROADMAP создавать запрещено.
