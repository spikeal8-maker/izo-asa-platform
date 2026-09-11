# IZO ASA · человеческая карта плана

Текущий active/next package и точный `branch_from` находятся только в [`PLAN.json`](PLAN.json) и
сгенерированном [`CURRENT.md`](CURRENT.md). Этот файл **не повторяет mutable статусы**, чтобы не становиться
вторым roadmap.

## Как читать план

- `PLAN.json` — machine source: packages, dependencies, lineage, active/next, frozen checkpoint.
- `CURRENT.md` — короткая текущая точка входа, генерируется из PLAN.
- `docs/reviews/<ID>.md` — evidence конкретного package.
- `docs/history/` — старые критерии и состояние; не default context.

## Стратегическое правило

Пакеты выполняются последовательно по зависимостям PLAN. Параллельная lineage не становится canonical по
номеру PR или дате. Если две реализации расходятся, сначала отдельный reconciliation package, затем feature work.

После зелёного exact-head CI checkpoint замораживается. Следующий package стартует новой веткой от frozen SHA;
переход active state происходит уже в новой ветке через `tools/project_state.py start`.

Предметные acceptance старых пакетов при необходимости читать в историческом NEXT только для конкретного ID,
а не загружать весь прежний roadmap.
