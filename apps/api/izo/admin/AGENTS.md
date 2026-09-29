# ADMIN-001 · ограниченные изменения

Наследует корневой AGENTS и apps/api/AGENTS. Задача: A-02/A-03, AD-01,
ограниченный A-29 и U-28. Полную CRM/настройки/управление доступом не добавлять.

- Права/identity/lock order: ../accounts/admin_access.py, test_admin.py.
- Сумма/номер заявки/DTO: schemas.py; current_password никогда не логировать.
- Команда: service.py вызывает только существующий CreditService.grant в общей
  транзакции. Не делать прямой SQL по wallet/ledger, не коммитить внутри Credits.
- HTTP: routes.py и общий ../accounts/http_security.py; tests/test_admin_http.py.
- UI: features/admin (без DemoState), U-28 — features/credits. Общий transport один.
- Ближайшая проверка: pytest tests/test_admin.py tests/test_admin_http.py
  tests/test_admin_boundaries.py; затем профильный admin.spec.ts phone+laptop.
- Перед приёмкой: полный CI и admin-live.mjs с настоящими web/API/PostgreSQL,
  before/after tools/admin_acceptance.py. Подставной API не доказывает live path.

Session/permission/cap/password повторно проверяются перед ledger command.
Порядок locks: отсортированные Accounts → session/permissions → policy → wallet.
Snapshot password проверяется заново после KDF, не держать транзакцию на весь KDF.
Номер business case стабилен при повторах; другой operation_id не даёт вторую
компенсацию по той же заявке. Unknown HTTP outcome не меняет номер заявки/операции.
Scope grants сейчас операторский глобальный, только минимальные metadata/credits;
private media, impersonation, roles editor и произвольные server commands отсутствуют.
CLI bootstrap только явный isolated development/test, никогда startup/signup.
Ограничение суммы — per grant, не дневной бюджет. Правила не ослаблять ради тестов.
