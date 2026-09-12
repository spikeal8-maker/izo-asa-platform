# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=access/staff-delegation@fbb3ba01232c0b31682db0f37a070300d95335ed -->
<!-- working_branch=settings/plan-policy -->
<!-- active_package=SETTINGS-002 -->
<!-- next_package=CATALOG-002 -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Следующий package стартует командой `python tools/project_state.py begin-next ...`: она проверяет GitHub PR
и required workflows текущего working head, создаёт новую ветку точно от этого head и только там меняет state.

Активный пакет: **SETTINGS-002**. Следующий: **CATALOG-002**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
