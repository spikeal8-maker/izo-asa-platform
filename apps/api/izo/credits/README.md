# Credits · локальная карта домена

Credits — единый серверный ledger продукта. Он владеет wallet projection, immutable ledger и reservations.
Admin использует grant/compensation, Jobs использует reserve/settle/release, web читает собственный баланс через
`GET /api/v1/credits`. Provider и UI не получают права самостоятельно менять деньги.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| Wallet / ledger / reservations | `tables.py`, repository helpers | `test_credits.py`, `test_credit_boundaries.py` |
| grant / reserve / settle / release | `service.py` | `test_credits.py` |
| Own balance/history HTTP | `routes.py` | `test_credits_http.py` |
| Migration / append-only guards | migration `0004_credits` | `test_credit_migration.py` |
| Web balance/history | `apps/web/src/features/credits/` | account/credits E2E coverage |

## Инварианты

- `balance`, `reserved` и `available` — server-owned integer values;
- reserve не является списанием; settle списывает только фактическую стоимость в пределах reserve;
- release закрывает reserve без нового начисления;
- browser не вызывает grant/reserve/settle/release напрямую и не присылает цену/actor;
- operation/case/request identities обеспечивают replay safety;
- Accounts locks берутся до wallet/reservation locks; provider network call не выполняется внутри ledger transaction.

## Текущие интеграции и границы

Admin compensation и Jobs settlement используют это же ядро; `/account/credits` показывает серверный журнал.
Нулевой баланс не запрещает читать разрешённые собственные данные. Реальные purchases/payment provider здесь
не реализуются: это отдельный Billing contract, который не должен подменять ledger command.

- credit semantics → `api.credits`;
- job admission/cancel/outcome → `api.jobs`;
- staff compensation → `api.admin`;
- plan/quota/cost cap → `api.entitlements`.

Текущие SHA/PR/roadmap не хранятся в local map. Историческая подробная версия сохранена в
`docs/history/local-maps-before-DOC-004C/credits.md`.
