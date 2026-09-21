# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=ux/frontend-reset@c3d9390c2e376ab4656714a9bceee522a7854477 -->
<!-- working_branch=ux/frontend-continuation -->
<!-- active_package=FRONTEND-002 -->
<!-- next_package=NONE -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Нормально принятый package продолжает `python tools/project_state.py begin-next ...`: команда проверяет PR и CI,
создаёт новую ветку точно от verified working head и только там меняет state. Если active package нельзя честно принять,
а canonical branch уже продвинулась независимыми verified merges, используется только explicit `reconcile-continuation`.

Активный пакет: **FRONTEND-002**. Следующий: **NONE**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
