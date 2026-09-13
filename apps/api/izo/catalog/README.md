# CATALOG-002 · versioned provider metadata

CATALOG — staff-only control plane поверх существующих ACCESS/SETTINGS/API слоёв.
Он хранит immutable capability/connection revisions, disabled published pointers,
offline proof, opaque credential binding metadata и idempotent audit receipts.

Сейчас code registry содержит canonical fal provider (`https://queue.fal.run`) и adapter
`fal.images.v1`. HTTP выбирает только approved IDs; произвольный endpoint и raw API key
не являются полями контракта. Credential stores только logical locator/fingerprint/scope/version.

`publish` не означает live activation: connection остаётся `disabled`, capability view имеет
`runtime_available=false`, proof имеет `network_called=false` и `live_ready=false`.
CATALOG-002 не хранит и не редактирует product price, plan image sizes, provider spend budget
или failover policy: эти поля остаются у Jobs/Entitlements/Fal runtime и будущего pricing package.
Текущий Jobs/Fal runtime продолжает использовать свой принятый execution contract;
его подключение к DB catalog требует отдельного решения и не делается CATALOG-002.

Ownership: schema/registry → `schemas.py`/`registry.py`; lifecycle → `service.py`;
persistence → `tables.py`/`repository.py`; HTTP → `routes.py`; PostgreSQL → `0011_catalog.py`.
