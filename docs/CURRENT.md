# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- branch_from=docs/agent-development-system@001edb9953d642f4d06453505809c20512f4b2b3 -->
<!-- working_branch=docs/maintenance-precision -->
<!-- active_package=DOC-004B -->
<!-- next_package=LINEAGE-001 -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Откуда продолжать

Новые изменения создаются только от **branch_from** выше. `runtime_base` — принятая runtime-основа,
но не обязательно последний development checkpoint. Текущая рабочая ветка — `working_branch`.

Активный пакет: **DOC-004B**. Следующий: **LINEAGE-001**.

Параллельные lineages из PLAN нельзя использовать как base без отдельного reconciliation.
Зелёный exact-head CI замораживает checkpoint: после него этот SHA не редактируется.
Следующий пакет начинает новая ветка от frozen SHA и переводит состояние через `tools/project_state.py start`.
