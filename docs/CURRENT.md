# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=main@95f153acc3a7a3ce4163d2e59b6f3e44ba963906 -->
<!-- working_branch=sub/prep1-integration-glue-001 -->
<!-- active_package=PRE-P1-STRUCTURAL-MAINTENANCE-001 -->
<!-- next_package=NONE -->

Это короткая точка входа после `AGENTS.md`. Live machine state — `PLAN.json`; package registry читается точечно через `project_state.py show-package <ID>`.

## Как продолжать

`working_branch` — canonical branch состояния. `current_package_base` — замороженный родитель для ancestry;
**не выбирать его вручную как base следующего package**.
Если `next_package` выбран — `begin-next`. Для `decides_next=true` + `next_package=NONE` —
`begin-decided-next`: exact HEAD/CI/review или explicit owner waiver проверяются до новой ветки, state пишется только
на ней. Для непринятого active package используется только `reconcile-continuation`.

Завершённый пакет: **PRE-P1-STRUCTURAL-MAINTENANCE-001**. Следующий: **NONE**.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
