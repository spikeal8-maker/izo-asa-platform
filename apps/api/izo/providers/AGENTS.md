# Providers · обязательные локальные правила

Наследует корневой `AGENTS.md`. Для provider-задачи сначала `README.md`, затем один adapter и его contract test.

- Не создавать provider-specific Account/Credits/Jobs/Media/Gallery.
- Secret value не хранится в DB/public DTO/log/error/artifact; adapter получает его только через approved resolver/env worker boundary.
- Не принимать arbitrary endpoint из browser/admin payload, если отдельный catalog policy это явно не разрешает.
- Submit timeout/5xx после возможной отправки = unknown outcome, если provider не доказал безопасную idempotency.
- Не делать automatic paid retry/failover из generic retry path.
- Persisted provider request ID продолжает тот же request после lease/restart; cancel semantics проверяются по provider contract.
- Любой provider URL/result считается недоверенным: HTTPS/host/redirect/size/MIME/dimensions bounds до codec/storage.
- 401/403/429/timeouts не маскируются под success; credential rotation не должна тайно менять identity уже принятого request.
- Unit tests используют fake transport и не открывают внешний network. Live call — отдельный owner-approved acceptance с budget.

После изменения: provider contract test → provider jobs/recovery test при lifecycle change → SELF_REVIEW → общий CI.
