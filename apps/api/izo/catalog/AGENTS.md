# CATALOG-002 · agent map

Читайте только нужный слой:
- `schemas.py` — HTTP/domain contracts;
- `registry.py` — approved providers/adapters/endpoints/secret locator policy;
- `service.py` — draft/proof/publish/credential lifecycle;
- `repository.py` + `tables.py` — immutable revisions, heads, receipts;
- `routes.py` — staff HTTP boundary.

Ближайшие тесты: `tests/test_catalog.py`, затем `tests/test_catalog_http.py`,
`tests/test_catalog_migration.py` и `tests/test_catalog_boundaries.py`.

Инварианты: raw secret никогда не хранится/возвращается; endpoint принадлежит code registry;
proof не делает сеть и всегда `live_ready=false`; connection publish остаётся `disabled`;
CATALOG не меняет `jobs.catalog`, `FalSettings` или durable provider execution.
Permissions приходят только через ACCESS-001: `catalog.read/write`, `connections.read/write`, `secrets.bind`.
Не добавлять arbitrary URL, live enable, key balancer, auto fallback или provider call в этот пакет.
