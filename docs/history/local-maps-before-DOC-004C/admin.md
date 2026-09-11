# ADMIN-001 · минимальная серверная админка

База: 1aba446b8b91752aeacd62f8291f851507d4cf14, PR #9. Это развитие Accounts/Credits,
не вторая авторизация, второй баланс или новый универсальный settings engine.

## Реализуемый объём

`/admin/users`: поиск имени/публичного кода (минимум3 символа), ограниченная выдача.
`/admin/users/{id}`: имя, код, состояние, подтверждение identity; с отдельным
`credits.read` — баланс и последние20 операций. API поддерживает cursor pagination.
`AD-01`: стабильный номер обращения, сумма, подтверждение получателя и текущий
пароль сотрудника. `/admin/audit`: ограниченный redacted журнал с pagination.
`/account/credits`: настоящие own balance/ledger через существующий GET credits.
Это не связывает DEMO-генерацию с серверными баллами и не меняет дизайн всей студии.

Полномочия проверяются backend для каждого чтения/команды. Оператору нужны
users.read_limited, для чужих средств дополнительно credits.read; для начисления
credits.grant и конечная действующая admin_grant_policy; audit.read отдельно.
Обычный пользователь не получает rights при регистрации, через тариф или JS.
Readonly видит только перечисленные metadata, не email/password/sessions/files.
Все staff commands требуют active/verified identity. Первоначально это явные
глобальные operator permissions; делегирование с per-user scopes — ACCESS-001,
не скрытая готовая функция. Ограничение/удаление пользователей AD-02, полный
A-04 search и A-05 case management ещё не реализованы.

## Компенсация и повторы

Номер дела содержит 3…64 ASCII символа, нормализуется в upper-case и преобразуется
в стабильный UUID5 namespace `izo-asa:relaunch-compensation:v1:`. Existing Credits
case uniqueness защищает тот же business case даже с новым operation key/получателем.
UUID5 здесь идентификатор, не секрет. Номер не должен содержать PII.

Grant actor берётся только из cookie session. Password KDF ограничен существующим
throttle и выполняется вне долгой транзакции; после него повторно проверяются
credential snapshot, session/CSRF, active/verified state, permissions и server cap.
Accounts берутся в едином порядке до session/wallet, в том числе при взаимных
действиях двух операторов. Результат: одна existing ledger command + admin event
в одной outer transaction. Ошибка audit откатывает весь grant. Повтор возвращает
original receipt; cap/revocation проверяются даже при replay. Cap — per-operation,
не дневной лимит/право бесконтрольно выдавать кредиты.

Журнал `admin_events` append-only на PostgreSQL (UPDATE/DELETE/TRUNCATE запрещены
триггером); приложение не обходит защиту для cleanup. Владельца БД с правом drop
trigger это не делает криптографически неподконтрольным оператором. Actor/target,
action/outcome, operation/case и время; без сырого пароля, email и body. Denied
known actors логируются отдельно после rollback; неизвестная/отозванная session
использует уже имеющуюся redacted HTTP-диагностику.

## API

GET /api/v1/admin/me — разрешённые права/конечный cap и CSRF текущей сессии.
GET /api/v1/admin/users?q=...&limit=20&after=UUID — ограниченный поиск.
GET /api/v1/admin/users/{id} — безопасная карточка.
GET /api/v1/admin/users/{id}/credits?limit=20&before=sequence — credit service read.
POST /api/v1/admin/users/{id}/compensations — operation_id, case_reference, amount,
current_password. Reason фиксирован compensation, actor/cap клиент не выбирает.
GET /api/v1/admin/audit?limit=20&before=UUID — события time+id keyset.

Мутации используют общий origin/JSON/CSRF и bounded body8192; validation не отражает
пароль в ответе. Denial не меняет баланс. Нет публичного reserve/settle, role editor,
SQL/shell или secret settings endpoint. Неизвестный outcome в форме сохраняет тот
же operation ID, стирает пароль и предлагает сверку/повтор, не создаёт новый case.

## Явное назначение оператора только на локальном стенде

Сначала создать аккаунт штатно и подтвердить email через существующую TEST-mail
процедуру AUTH-002. Получить UUID из своего /account API. Затем оператор среды
вызывает модуль `izo.admin.bootstrap` с обязательными --account и --grant-limit
и `IZO_ADMIN_BOOTSTRAP=isolated`. Модуль принимает только development/test Settings,
существующий active verified account и впервые выдаваемый набор permissions.
Нет default cap; сумма задаётся явно, не считается согласованным тарифом.

Справка без изменения БД:

```sh
docker compose run --rm api python -m izo.admin.bootstrap --help
```

Это не production bootstrap и не удалённый запрос прав. Повторное назначение не
обновляет existing grants; ACCESS-001 введёт отдельные reviewed команды управления.

## Проверки и границы

Unit: test_admin.py, test_admin_http.py, test_admin_boundaries.py; SQLite/ASGI,
настоящие AuthService/CreditService, network blocked. Негативные случаи, rollback,
двойной case, scopes, password/session/cap changes после KDF.

GitHub: прежний полный CI сохранён, добавлены PostgreSQL races/restart и настоящий
Playwright login → search → grant → reload → own credits → nonstaff denied. Эти
проверки используют только явно synthetic accounts и защищённый RUNNER_TEMP.
Картинки live evidence не содержат паролей; реальные users/keys/API не используются.
Готовность фиксировать по exact commit/steps, не по существованию этих скриптов.

Подтверждённые требования безопасности:
https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
https://www.postgresql.org/docs/current/explicit-locking.html

Незакрыто: production/MFA/публичная доставка почты/полное staff delegation, privacy
cleanup/нагрузка/независимое review/branch protection. Не выдавать UI admin за весь
каталог30 страниц и66 групп настроек. Следующий предметный пакет — MEDIA-001.
