# Backend · правила ограниченной разработки

Наследует корневой `AGENTS.md`. Сначала выбери context route; затем локальный AGENTS/README домена,
конкретный service/table/route и профильный test. Не читать весь web/docs для серверной команды.

| Домен | Локальная карта | Ближайшие tests |
|---|---|---|
| Accounts/Auth | `izo/accounts/README.md` | `test_accounts.py`, `test_auth_boundaries.py` |
| Admin | `izo/admin/AGENTS.md`, `izo/admin/README.md` | `test_admin*.py` |
| Credits | `izo/credits/AGENTS.md`, `izo/credits/README.md` | `test_credits.py`, `test_credit_boundaries.py` |
| Entitlements | `izo/entitlements/AGENTS.md`, `README.md` | `test_entitlements.py`, `test_entitlement_boundaries.py` |
| Media | `izo/media/AGENTS.md`, `README.md` | `test_media*.py` |
| Jobs | `izo/jobs/AGENTS.md`, `README.md` | `test_jobs*.py` |
| Providers | `izo/providers/AGENTS.md`, `README.md` | `test_fal_provider.py`, `test_provider_jobs.py` |

## Backend invariants

Migrations — только новые forward revisions; не `create_all` production startup и не правка старой migration.
Account/ownership/permission/credits invariants проверяются сервером под ожидаемыми locks/transactions.
SQLite unit не доказывает PostgreSQL locking/restart; risk-bearing path должен иметь соответствующий CI/integration gate.

Изменённый public API экспортируется из кода и проверяется canonical OpenAPI. Secret/token/password/proof не попадает
в JSON ошибок/log/artifacts. External network в unit запрещён. Не ослаблять tests/rate/size/retry bounds ради PASS.

После изменения: профильный test → boundary/HTTP/migration test по риску → SELF_REVIEW → общий CI.
