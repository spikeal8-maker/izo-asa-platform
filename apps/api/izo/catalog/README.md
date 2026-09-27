# Catalog owner

This domain owns the finite approved provider/model list, publication state,
informational RUB display prices, global revision and durable change audit.
`service.py` checks staff permissions in Accounts; `routes.py` exposes only the
typed Admin API. Chat reads the published text snapshot during policy and
request admission. Image metadata does not control Jobs until a separate
integration package. The Credits ledger and provider credentials are outside
this owner. Null price means unknown, never free. Null is allowed only for the
current Chat BYOK preview: Chat does not debit Credits, while the external
provider may still charge the user's key. A future platform-funded paid flow
must reject null before its server-owned quote and admission. Prices here are
informational RUB display metadata. Replaying a
PATCH operation with the same ID and body applies no new change and returns
the current catalog snapshot, which may include later staff changes. A missing
PostgreSQL seed fails closed; SQLite metadata.create_all fixtures can seed
the finite defaults. Nearest tests: `test_catalog.py`, `test_catalog_http.py`,
`test_catalog_migration.py`, `test_chat_catalog.py`.

Successful PATCH commands append an immutable catalog event with the revision,
actor, reason and before/after metadata. Non-anonymous denials append a
redacted Admin event without request body, key or price values.

## Existing local owner

An ACCESS owner enrolled before `pricing.write` was added has no delegation
ceiling for it. A local operator must explicitly run
`AccessService(auth).upgrade_local_owner_permission(owner_id, "pricing.write")`
in a one-shot development/test Python process with
`IZO_ACCESS_BOOTSTRAP=isolated` and the configured PostgreSQL connection.
The method accepts only a verified active owner with a permanent
`access.manage` grant, ceiling and materialized permission. It writes the
new permanent grant, ceiling, materialized permission, state version and
admin audit atomically; replay is a no-op. It is not called by migration,
startup or HTTP. The operator should then verify `pricing.write` in the
owner's access view before editing prices.
