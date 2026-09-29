# ADR-001 · Каноническая provider-линия

**Статус:** superseded for post-reconciliation routing by ADR-002
**Дата:** 2026-09-11
**Решение относится к:** API-001 и всем пакетам, зависящим от provider/catalog/settings runtime.

## Контекст

После CHANGE-001 появились две реализации API-001. Одна линия использовала OpenRouter и стала базой для
SETTINGS-001/CATALOG-001. Позже API-001 был заново реализован через fal.ai с отдельным durable request lifecycle
и полным exact-head CI. Обе линии остались открытыми Draft PR, поэтому «самая новая ветка» или номер PR не дают
однозначного ответа, откуда продолжать разработку.

## Решение

Для автоматического продолжения проекта канонической технической базой считается линия fal.ai,
зафиксированная в `docs/PLAN.json`. OpenRouter lineage получает статус `hold_for_reconciliation`.

Ни один coding-agent не должен:

- автоматически ветвиться от OpenRouter-derived SETTINGS/CATALOG;
- считать их удалёнными или бесполезными;
- cherry-pick/rebase provider-specific код без анализа;
- строить новый feature поверх обеих линий одновременно.
## Последствия

Следующий после DOC-004 пакет — LINEAGE-001. Он должен сравнить обе линии по domain boundaries, migrations,
settings/catalog metadata, secret model, UI и tests. Provider-neutral части можно перенести на fal lineage;
OpenRouter-specific assumptions либо адаптируются отдельным решением, либо остаются historical.

До завершения LINEAGE-001 статусы SETTINGS-001/CATALOG-001 в `PLAN.json` — `parallel_lineage_only`.
Это не означает, что их технические CI-results ложные; это означает, что они не определяют текущую архитектуру.

## Почему не «выбрать по номеру PR»

PR — транспорт review, а не архитектурный source of truth. Несколько Draft PR могут быть технически зелёными и
при этом несовместимыми как база следующей работы. Каноничность задаёт PLAN + ADR, а exact correctness конкретного
SHA подтверждают его Checks/review.

## Как изменить это решение

Новый ADR с явной причиной, сравнением и migration/rebase plan. Простого изменения CURRENT/PR body недостаточно.
