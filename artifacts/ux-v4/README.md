# IZO ASA UX v4 — compact staging handoff

Статус: **non-canonical staging**.

Этот каталог сознательно сокращён после критического анализа. Он больше не должен быть параллельной системой PRODUCT/UX/ADMIN. Его задача — временно хранить один качественный implementation handoff до переноса принятых фактов в canonical docs.

## Читать в таком порядке

1. `QUALITY_IMPLEMENTATION_SPEC.md` — единое качественное ТЗ на UX/product implementation.
2. `DECISIONS.md` — только реальные pending owner decisions; ближайшие и отложенные разделены.
3. `CONTROL_PLANE_REPAIR_SPEC.md` — lifecycle #188 + independent-review identity hardening.
4. `CRITICAL_ANALYSIS.md` — почему была проведена нормализация и какие риски остаются.
5. `STAGING_STATUS.json` — короткий machine-readable status.

Других active coordination docs в этом каталоге быть не должно. Новая заметка создаётся только если она заменяет один из документов выше, а не дублирует его.

## Source snapshot

- repository: `spikeal8-maker/izo-asa-platform`
- frozen product source: `ux/frontend-reset@5c0e79b6fc3a7120207d0889b176fbfed3dab973`
- PR: `#36 FRONTEND-001`
- current technical CI: green for exact source
- owner visual acceptance: pending
- independent review: pending
- lifecycle issue #188: open

## Что это ТЗ не делает

- не меняет `PLAN.json`/`CURRENT.md`;
- не активирует FRONTEND-002;
- не заменяет `PRODUCT.md`, `UX.md`, `ARCHITECTURE.md`, `ADMIN.md`;
- не объявляет Video/Audio/3D runtime существующим;
- не считает 75/75 registry coverage готовностью;
- не разрешает fake Chat/tool success;
- не разрешает обход review/lifecycle gates.

## Promotion path

После закрытия текущих gates:

1. исправить/разрешить control-plane repair;
2. перенести принятые Chat-first/product route facts в canonical `PRODUCT.md`;
3. перенести visual/responsive facts в `UX.md`;
4. устранить duplicate ownership `UX_PRODUCT_SHELL.md`;
5. выполнить маленький Chat reconciliation package;
6. после этого развивать конкретные domain capabilities отдельными packages.

## История

Предыдущие промежуточные UX-v4 coordination docs и архивная сборка остаются доступны в истории этой staging-ветки. Они намеренно удалены из текущего HEAD, чтобы coding-agent не получал десятки конкурирующих документов как live context.

Правило качества: **одна задача — один owner — маленький scope — проверяемые acceptance cases — один canonical владелец факта.**
