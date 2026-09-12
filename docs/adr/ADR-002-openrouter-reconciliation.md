# ADR-002 · Reconciliation OpenRouter → canonical fal

**Статус:** accepted for post-reconciliation development routing  
**Дата:** 2026-09-12  
**Заменяет для дальнейшего routing:** ADR-001 после завершения LINEAGE-001.

## Контекст

Канонический API-001 уже реализован на fal.ai (`fal.flux2.klein.4b`) с durable provider-call lifecycle.
Параллельно сохранилась OpenRouter-линия: API-001 PR #15/#16/#17, SETTINGS-001 PR #19,
CATALOG-001 backend PR #20 и Catalog UI PR #21. Продолжать от любой из этих веток автоматически запрещалось
до предметного сравнения кода, migrations, permissions, provider coupling, UI и CI.

## Решение

Канонической provider-линией остаётся **fal.ai**. Ни один OpenRouter provider/client/worker/runtime resolver
не переносится в current runtime и не становится fallback. Старые PR остаются только reference evidence.

SETTINGS-001 PR #19 содержит полезную provider-neutral модель typed `PlanPolicy` lifecycle: preview,
optimistic publish, immutable history и rollback-as-new-revision. Но пакет вводил `plans.write` без
канонического provisioning/delegation lifecycle. Поэтому код не cherry-pick-ится; он re-author reference для
нового `SETTINGS-002` после `ACCESS-001`.
CATALOG-001 PR #20 доказал полезные patterns: immutable capability/connection revisions, optimistic versions,
offline proof, opaque credential references, rotation/revoke и audit receipts. Но schema/runtime жёстко фиксировали
OpenRouter endpoint, adapter ID, env key и заменяли public Job admission своим OpenRouter resolver. Эти части
не совместимы с уже принятым fal lifecycle. Новый `CATALOG-002` должен быть provider-neutral metadata/control
plane и **не подменять** `jobs.catalog`, `FalSettings` или durable provider calls без отдельного contract decision.

Catalog UI PR #21 не является принятой реализацией: Foundation CI завершился failure на permission/navigation
сценариях catalog-only staff. UI-паттерны operation-id reuse, no-raw-secret forms и explicit disabled/live state
можно использовать как reference; код re-author-ится как `CATALOG-UI-002` после нового backend.

Старая migration `0010_catalog.py` не переносится byte-for-byte. Каноническая 0010, если понадобится в
`CATALOG-002`, создаётся заново от текущего `0009_provider_calls` и описывает только новую neutral schema.

## Новый порядок

1. `ACCESS-001` — bounded staff delegation/provisioning для новых granular permissions.
2. `SETTINGS-002` — typed basic-plan lifecycle на текущем Entitlements storage.
3. `CATALOG-002` — neutral catalog metadata для fal и будущих adapters.
4. `CATALOG-UI-002` — permission-correct admin UI.

OpenRouter PR/branches не закрываются и не merge-ятся автоматически этим ADR; они просто перестают быть
development bases. Live provider spend, merge и deploy остаются отдельными owner actions.
