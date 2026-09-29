# AUTH-001: серверные аккаунты

Реализуемый scope: U-02/U-03/U-26, общий Account/Identity/Session и минимальная
проверка permissions. Это dev/test, не разрешение публичного запуска. Нет почты,
подтверждения email, recovery, Telegram/MAX signed login, MFA, платежей или генерации.
Новая identity сохраняется с `verified_at=NULL`; роль и баланс не вводятся клиентом.

## Реальные маршруты

- POST `/api/v1/auth/register`: email, password, display_name, invite_code → 201,
  серверная cookie, account и CSRF. Приглашение одноразовое, целиком в транзакции.
- POST `/api/v1/auth/login`: email/password → новая cookie, account и CSRF.
- GET `/api/v1/auth/me`: текущая проверенная identity и CSRF; без сессии 401.
- GET `/api/v1/auth/sessions`: только активные сессии данного аккаунта.
- POST `/api/v1/auth/logout`, POST `/api/v1/auth/sessions/revoke-others`,
  DELETE `/api/v1/auth/sessions/{session_id}`: защита Origin + CSRF, ответ 204.

Публичного API выдачи приглашений или staff permissions нет. Вход не принимает
роль из Telegram globals, HTTP headers, localStorage или адреса страницы.
Формы `/login`, `/register`, `/account` и `/account/sessions` используют эти API.
Browser E2E с fake routes проверяют UI; реальная БД/HTTP проверяются отдельным
Compose-тестом. Нельзя смешивать доказательства этих уровней.

## Запуск локального стенда

В новом checkout:

```sh
python tools/bootstrap.py
docker compose up --build --wait
docker compose run --rm api python -m izo.accounts.invites --hours 24
```

Открыть `http://localhost:8080/register` и ввести выданное одноразовое приглашение.
Команда намеренно показывает приглашение один раз; его нельзя отправлять в
публичный issue/log. Для ещё одного аккаунта выпустить отдельное приглашение.

У ранее созданного `.env` сначала добавить только новые auth-настройки:

```sh
python tools/bootstrap.py --auth-only
docker compose up --build --wait
```

Команда не заменяет существующие DB/S3/auth secrets. Не удалять volumes и .env
ради обновления. Для неготового/пустого rate-secret auth возвращает 503; health
сервера отдельно. Закрытая регистрация по умолчанию в коде disabled; bootstrap
нового dev-стенда явно включает только invite, не public signup.

## Защита и границы

Пароль: versioned scrypt, N32768/r8/p3 (32 MiB), random salt16, digest32, constant-time
comparison; 15…128 символов при регистрации, максимум512 UTF-8 bytes, без усечения.
Два одновременных KDF на процесс, перегрузка → 429. Изменение алгоритма требует
версионного verifier/re-hash плана, не редактирования параметров на старых хэшах.

Bearer: 32 random bytes, в БД только SHA-256; отдельный случайный CSRF хранится
в серверной сессии и передаётся JS через JSON, затем в X-CSRF-Token. Он не заменяет
bearer и не даёт вход сам по себе. Cookie host-only/HttpOnly/SameSite=Lax; HTTPS
профиль использует Secure и __Host-. HTTP разрешён только loopback dev; общий
production режим приложения по-прежнему выключен.

Все мутации требуют точного configured Origin и X-IZO-Request:web, auth-body ≤8192
байт, включая chunked. Logout/revoke требуют session-bound CSRF. CORS не открыт.
Формат входа строго запрещает дополнительные поля; ошибочные payloads не включают
пароль/приглашение в response. GET me/session не выдаёт cookie или password hash.

Rate limit — атомарные PostgreSQL counters в **фиксированном окне**, subject+peer
за HMAC отдельного секрета. Default5/300 секунд на subject и100/300 на transport peer,
без сброса после неверного пароля. Не считать это sliding-window или готовой защитой
от DDoS. Не доверяем X-Forwarded-For клиента; за нынешним Caddy peer может быть общим
для клиентов. Перед публичным выпуском нужны trusted proxy/edge limits и нагрузочная
проверка, не незаметное доверие произвольному header.

Сессии: idle1800, absolute604800, максимум10 активных; сроки Unix UTC. Абсолютный
срок не продлевается активностью; ужесточение policy применяется при следующей
проверке. Account row locks сериализуют создание/отзыв. Утраченная/просроченная или
отозванная сессия возвращает401; чужой session ID при отзыве —404. Permissions
перечитываются из БД, истёкший/удалённый grant не хранится в cookie.
Проверка staff permission дополнительно требует active-состояния аккаунта.

Аудит фиксирует регистрацию, создание/отзыв сессий и выдачу приглашения без секретов.
Полный security audit не заявляется: неуспешные HTTP-запросы пока видны в безопасном
request log. Административное делегирование, общая матрица restricted-account
операций, cleanup накопившихся revoked sessions и retention вводятся своими этапами.
Email поддерживает документированный ASCII mailbox subset; SMTPUTF8 не реализован.

DemoProvider не читает реальную сессию и не становится ledger. Работы нынешней
галереи остаются демо вкладки; серверная регистрация их не переносит и не защищает
как настоящие private assets. Для этого нужны CREDIT/MEDIA/JOBS.

## Проверки и экономный маршрут

```sh
python -m pytest tests/test_accounts.py tests/test_auth_boundaries.py
python tools/export_contracts.py --check
```

Unit использует SQLite in-memory и fake clock, не подтверждает PG locks. В GitHub
`tools/auth_acceptance.py before/after` проверяет настоящие API+PostgreSQL: одновременная
регистрация, одноразовость, account/session cap, atomic counters и реальное Compose
down/up. Тестовые cookie временно передаются через private RUNNER_TEMP, не artifact,
не platform_metadata; credentials реальных пользователей не используются. Скрипт
отказывается работать без test environment, заданного test DB и explicit opt-in.

Контракты OpenAPI экспортируются инструментом; TypeScript types генерируются
существующей сборкой. Для auth-кнопки читать accounts UI + test, для revocation —
service + соответствующий тест, не весь проект. Миграция0002 добавляет таблицы,
0001 неизменна. После acceptance продолжать AUTH-002/credits по NEXT, не писать
вторую систему identity ради следующего провайдера.

Основания проверены 2026-09-08:
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- https://www.psycopg.org/psycopg3/docs/basic/transactions.html
