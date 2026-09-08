# Backend: ограниченная разработка

Наследует корневой AGENTS. Не читать все UI/документы для серверной команды.

Accounts: `izo/accounts/schemas.py` — вход/выход; `service.py` — правила;
`repository.py` и `tables.py` — SQL; `routes.py` — cookie/origin/CSRF;
`security.py` — пароль/случайные токены; `settings.py` — политика.
Команды проверки: `python -m pytest tests/test_accounts.py tests/test_auth_boundaries.py`,
затем `python tools/export_contracts.py --check`. PostgreSQL races/restart — отдельный
изолированный Compose gate, SQLite unit не доказывает PostgreSQL locking.

Пароль/приглашение/session bearer не публикуются в JSON ошибок, logs или artifacts.
DTO не принимает role, owner, permissions и balance. Principal определяется по
серверной сессии; permissions читаются заново, не из браузера. Защитные правила
не отключаются ради интеграции провайдера. Регистрация не назначает staff.

Миграции неизменяемы после принятия; следующая — новый файл. Никаких create_all
или upgrade на startup. Изменённый API экспортируется из кода, не редактируется
второй независимой TypeScript-копией. Сначала профильный тест, полный CI — на
готовом пакете. Не обновлять зависимости без причины. Увеличение task scope
и изменение CI требует явного объяснения, не скрытого обхода failed test.
