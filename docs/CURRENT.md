# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=docs/chat-v4-adoption-001@811410e3cada4498161415bc279ce9a9f033ab6a -->
<!-- working_branch=maint/pre-p1-stabilization-001 -->
<!-- active_package=PRE-P1-STABILIZATION-001 -->
<!-- next_package=NONE -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Если `next_package` выбран — `begin-next`. Для `decides_next=true` + `next_package=NONE` —
`begin-decided-next`: exact HEAD/CI/review или explicit owner waiver проверяются до новой ветки, state пишется только
на ней. Для непринятого active package используется только `reconcile-continuation`.

Активный пакет: **PRE-P1-STABILIZATION-001**. Следующий: **NONE**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
