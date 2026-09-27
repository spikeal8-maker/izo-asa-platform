# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=codex/admin-donor-catalog-001@ed1f79a6c53bdc3cab5d827d308ee661a61ebd20 -->
<!-- working_branch=codex/chat-ux-001 -->
<!-- active_package=CHAT-UX-001 -->
<!-- next_package=NONE -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Если `next_package` выбран — `begin-next`. Для `decides_next=true` + `next_package=NONE` —
`begin-decided-next`: exact HEAD/CI/review или explicit owner waiver проверяются до новой ветки, state пишется только
на ней. Для непринятого active package используется только `reconcile-continuation`.

Активный пакет: **CHAT-UX-001**. Следующий: **NONE**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
