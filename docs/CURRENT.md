# IZO ASA · текущая точка разработки

<!-- runtime_base=api/fal-klein-001@faec39d6ae0b4f035ef0f86114494789acde3b46 -->
<!-- current_package_base=maint/repository-modularity@731105b1c8d16d9774c987a31b62ee7143383ccc -->
<!-- working_branch=feat/guest-trial -->
<!-- active_package=GUEST-001 -->
<!-- next_package=NONE -->

Это короткая точка входа после `AGENTS.md`. Machine source of truth — `PLAN.json`.

## Как продолжать

Текущий package разрабатывается только в **working_branch**. `current_package_base` — его уже замороженный
родитель и используется для ancestry-проверки; **не выбирать его вручную как base следующего package**.
Следующий package стартует только после зелёных required workflows текущего package и отдельного выбора owner,
потому что `GUEST-001` имеет `decides_next=true`.

Активный пакет: **GUEST-001**. Следующий: **NONE**.
Цель текущего пакета — один ограниченный server-owned image trial до регистрации с abuse controls и переносом
того же owner/job/asset в аккаунт при регистрации. Реальный внешний provider spend в этот package не входит.
Параллельные lineages из PLAN нельзя использовать как base без reconciliation.
