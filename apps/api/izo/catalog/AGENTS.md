# CATALOG-001 · узкая область

Читайте `schemas.py` для полей, `tables.py` для persistence, `service.py` для lifecycle,
`routes.py` для staff HTTP. Ближайшие tests: `tests/test_catalog.py`, затем
`tests/test_catalog_http.py` и `tests/test_catalog_migration.py`.

Catalog не хранит raw provider key и не меняет Credits/Account/Media. Endpoint OpenRouter
берётся из adapter registry, а не из пользовательского поля. Contract proof не делает сеть
и всегда `live_ready=false`. Публикация connection оставляет runtime_state=disabled;
включение live требует отдельного разрешённого probe/budget и не добавляется обходом guard.

Credential binding хранит source/ref/scope/version, но HTTP response возвращает только
fingerprint ref. Rotate/revoke требуют fresh password и `secrets.bind`; старый proof после
rotation недействителен. Unknown field вроде api_key/token/endpoint отклоняется Pydantic.
Не добавлять key-balancer, arbitrary URL, env scan, provider fetch из API или auto fallback.
