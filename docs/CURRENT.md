# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=settings/plan-policy@220d302dc238889da066c1799652d4b036007de3 -->
<!-- working_branch=catalog/versioned-provider -->
<!-- active_package=CATALOG-002 -->
<!-- next_package=CATALOG-UI-002 -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Следующий package стартует командой `python tools/project_state.py begin-next ...`: она проверяет GitHub PR
и required workflows текущего working head, создаёт новую ветку точно от этого head и только там меняет state.

Активный пакет: **CATALOG-002**. Следующий: **CATALOG-UI-002**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
