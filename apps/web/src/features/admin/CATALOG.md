# CATALOG-001 UI · A-08…A-12

Этот каталог — административная поверхность существующего server Catalog. Он не является вторым runtime registry.

- `CatalogPage.tsx` маршрутизирует `/admin/models`, `/admin/providers`, `/admin/credentials` по реальным permissions из `/auth/me`; server endpoint всё равно повторно проверяет permission.
- `CatalogModelPage.tsx`: capability draft → offline proof → connection metadata publish → capability metadata publish/disable. `network_called=false` и `live_ready=false` показываются явно.
- `CatalogConnectionPage.tsx`: только allowlisted connection metadata. Provider endpoint фиксирован adapter-кодом и не редактируется браузером. Published connection остаётся runtime `disabled`.
- `CatalogCredentialPage.tsx`: только logical `secret_ref` и server fingerprint. Raw API key не принимается, не отображается и не сохраняется в browser storage. Bind/rotate/revoke требуют `secrets.bind`, `connections.write` и fresh password; password очищается после каждой попытки.

Mutation operation ID создаётся до запроса и не меняется после неизвестного ответа; редактирование payload создаёт новый ID. Нельзя добавлять кнопку live enable, direct provider fetch, localStorage secret, произвольный endpoint или «успешный probe» без соответствующего backend-пакета и отдельного разрешённого live acceptance.

Ближайшие проверки: `tests/test_catalog_ui_boundaries.py`, затем `e2e/catalog-admin.spec.ts` на phone/laptop; полный viewport CI — перед технической приёмкой. Playwright mock API проверяет UI-протокол, но не заменяет backend PostgreSQL acceptance из PR #20.
