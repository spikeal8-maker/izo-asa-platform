# IZO ASA UX v4 — compact staging handoff

Статус: **non-canonical staging**.

Этот каталог сознательно сокращён после критического анализа. Он не является параллельной системой `PRODUCT/UX/ADMIN` и не должен использоваться как постоянный source of truth. Его задача — временно хранить один качественный implementation handoff до переноса принятых фактов в canonical docs.

## Активный набор

В текущем HEAD должно быть ровно шесть файлов:

1. `README.md` — этот индекс и правила чтения.
2. `QUALITY_IMPLEMENTATION_SPEC.md` — полное human/reviewer ТЗ.
3. `DECISIONS.md` — только реальные pending owner decisions.
4. `CONTROL_PLANE_REPAIR_SPEC.md` — lifecycle #188 + review-evidence hardening.
5. `CRITICAL_ANALYSIS.md` — причины нормализации и оставшиеся риски.
6. `STAGING_STATUS.json` — короткий machine-readable status.

Новый coordination-документ не создаётся, если он не заменяет один из этих владельцев.

## Как читать

### Owner / reviewer

`README -> QUALITY_IMPLEMENTATION_SPEC -> DECISIONS`.

`CONTROL_PLANE_REPAIR_SPEC` читать только для lifecycle/review-gate работ. `CRITICAL_ANALYSIS` — rationale, а не implementation contract.

### Coding-agent

**Не читать все шесть файлов и не грузить полный `QUALITY_IMPLEMENTATION_SPEC.md` по умолчанию.** Старт остаётся canonical:

`AGENTS.md -> docs/CURRENT.md -> project_state verify -> block/route owner -> nearest test`.

Staging используется только если задача явно относится к подготовленному UX-v4 handoff. Тогда читать только нужные разделы:

- Chat/shell reconciliation: `QUALITY_IMPLEMENTATION_SPEC` §§4–6, 12–15, 17;
- Image/UI regression: §§4, 7, 12–13, 15, 17;
- Jobs/Gallery/Feed: §§4, 8, 12–13, 15, 17;
- Video/Audio/3D planning: §9 + соответствующий пункт `DECISIONS.md`;
- route decision: §5 + `DECISIONS.md` D-01…D-03;
- lifecycle/review tooling: только `CONTROL_PLANE_REPAIR_SPEC.md` + canonical process docs/source/tests.

Нельзя передавать весь staging-каталог как default prompt маленькой правки.

## Source snapshot

- repository: `spikeal8-maker/izo-asa-platform`;
- frozen product source: `ux/frontend-reset@5c0e79b6fc3a7120207d0889b176fbfed3dab973`;
- PR: `#36 FRONTEND-001`;
- exact-head technical CI: green;
- owner visual acceptance: pending;
- independent review: pending;
- lifecycle issue #188: open;
- product-decision tracker #189: open.

## Что staging не разрешает

- менять `PLAN.json`/`CURRENT.md` на frozen source;
- активировать `FRONTEND-002`;
- заменять canonical `PRODUCT.md`, `UX.md`, `ARCHITECTURE.md`, `ADMIN.md`;
- объявлять Video/Audio/3D runtime существующим;
- считать registry coverage готовностью;
- показывать fake Chat/tool success;
- обходить review/lifecycle gates;
- реализовывать D-01…D-03 до explicit owner decision + canonical reconciliation.

## Promotion path

После закрытия текущих gates:

1. исправить/разрешить control-plane repair;
2. перенести принятые Chat-first/product route facts в canonical `PRODUCT.md`;
3. перенести visual/responsive facts в `UX.md`;
4. устранить duplicate ownership `UX_PRODUCT_SHELL.md`;
5. выполнить маленький Chat reconciliation package;
6. после этого развивать конкретные domain capabilities отдельными packages.

## История и ссылки

Предыдущие промежуточные UX-v4 coordination docs и архивная сборка сохранены в Git history, но удалены из текущего HEAD. PR/issue coordination должна ссылаться только на текущие шесть файлов, чтобы не оставлять dead links на удалённые staging-документы.

Правило качества: **одна задача — один owner — маленький scope — проверяемые acceptance cases — один canonical владелец факта.**