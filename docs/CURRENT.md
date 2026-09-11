# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=docs/maintenance-precision@fe47e208809b5950b08c7133ba922d7be5742d24 -->
<!-- working_branch=docs/continuation-safety -->
<!-- active_package=DOC-004C -->
<!-- next_package=LINEAGE-001 -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Следующий package стартует командой `python tools/project_state.py begin-next ...`: она проверяет GitHub PR
и required workflows текущего working head, создаёт новую ветку точно от этого head и только там меняет state.

Активный пакет: **DOC-004C**. Следующий: **LINEAGE-001**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
