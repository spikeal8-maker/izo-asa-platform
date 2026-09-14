# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=maint/agent-economy@37baf419c45970d02ce1fab75aea15cc9e8269a0 -->
<!-- working_branch=ux/frontend-reset -->
<!-- active_package=FRONTEND-001 -->
<!-- next_package=NONE -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Следующий package стартует только после технической и визуальной приёмки FRONTEND-001: текущий frontend reset
должен остаться отдельным frozen checkpoint, а дальнейшие Feed/Chat/Video/Catalog пакеты не должны разрастаться поверх непринятой оболочки.

Активный пакет: **FRONTEND-001**. Следующий: **NONE**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
