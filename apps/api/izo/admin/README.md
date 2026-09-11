# Admin · локальная карта домена

Admin — staff-поверхность над общими Accounts и Credits. Домен владеет проверкой staff permissions,
ограниченным поиском пользователей, чтением разрешённых credit-данных, компенсацией и audit events.
Он не создаёт вторую авторизацию, второй баланс или универсальный settings engine.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| Staff access / user search / user card | `service.py`, `routes.py` | `test_admin.py`, `test_admin_http.py` |
| Compensation command | `service.py` + `../credits/service.py` | `test_admin.py`, `test_admin_boundaries.py` |
| Audit events / append-only rules | `tables.py`, repository helpers | `test_admin_boundaries.py` |
| Isolated operator bootstrap | `bootstrap.py` | профильные admin tests |
| Web UI | `apps/web/src/features/admin/` | `apps/web/e2e/admin.spec.ts` |

## Инварианты

- actor берётся из действующей staff session; role/permission/cap из browser не принимаются;
- `credits.read`, `credits.grant`, `audit.read` проверяются отдельно;
- compensation использует существующий Credits ledger и один business case, а не прямую запись баланса;
- password/secret/private session data не попадают в audit/public responses;
- denied/replay/concurrent команды не создают второй grant;
- обычный пользователь не получает staff permissions через тариф, регистрацию или UI.

## Когда расширять контекст

- только staff/user/audit → оставайся в `api.admin`;
- reserve/settle/release/ledger semantics → `api.credits`;
- account/session/password state → `api.accounts`;
- UI search/grant layout → `web.admin`.

Полный catalog будущих admin pages принадлежит `docs/ADMIN.md`, но для локальной команды он не читается
по умолчанию. Точные текущие package/CI/branch факты находятся только в PLAN/CURRENT/STATUS, не здесь.
Историческая подробная версия этого README сохранена в `docs/history/local-maps-before-DOC-004C/admin.md`.
