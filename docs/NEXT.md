# IZO ASA · человеческая карта плана

Текущий active/next package, `current_package_base`, working branch и next-branch policy находятся только в
[`PLAN.json`](PLAN.json) и сгенерированном [`CURRENT.md`](CURRENT.md). Этот файл **не повторяет mutable статусы**,
чтобы не становиться вторым roadmap.

## Как читать план

- `PLAN.json` — machine source: packages, dependencies, lineage, active/next, frozen checkpoint.
- `CURRENT.md` — короткая текущая точка входа, генерируется из PLAN.
- `docs/reviews/<ID>.md` — evidence конкретного package.
- `docs/history/` — старые критерии и состояние; не default context.

## Стратегическое правило

Пакеты выполняются последовательно по зависимостям PLAN. Параллельная lineage не становится canonical по
номеру PR или дате. Если две реализации расходятся, сначала отдельный reconciliation package, затем feature work.

После зелёных required PR workflows current working head замораживается как source checkpoint; PR evidence
фиксируется как `pr_merge_tree`, если workflow реально checkout-ил synthetic merge. Следующий package запускает
`tools/project_state.py begin-next`, который сам проверяет evidence/dependencies и создаёт ветку от frozen source head.

Предметные acceptance старых пакетов при необходимости читать в историческом NEXT только для конкретного ID,
а не загружать весь прежний roadmap.
