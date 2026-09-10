# Backend: ограниченная разработка

Наследует корневой AGENTS. Не читать все UI/документы для серверной команды.

Accounts: `izo/accounts/schemas.py` — вход/выход; `service.py` — правила;
`repository.py` и `tables.py` — SQL; `routes.py` — cookie/origin/CSRF;
`security.py` — пароль/случайные токены; `settings.py` — политика.
Команды: `python -m pytest tests/test_accounts.py tests/test_auth_boundaries.py`,
затем `python tools/export_contracts.py --check`.

AUTH-002: `accounts/EMAIL.md` — контракт; `challenge_schema/policy/tables.py` — DTO/политика/SQL;
`challenges.py` — транзакции; `challenge_routes.py` — HTTP; `test_mail.py` — только
операторский тестовый просмотр. Ближайшие tests: `test_email_proofs.py` и
`test_email_boundaries.py`; PG races/restart — `tools/email_acceptance.py` в CI.
Для правки формы не читать весь runtime и каталог провайдеров.

Пароль/приглашение/bearer/proof не публикуются в JSON ошибок, logs или artifacts.
Публичного test mailbox API нет. Новая ссылка не меняет пароль, GET не потребляет proof;
успешный reset отзывает sessions/proofs в одной транзакции. Не выдавать права по
client role, initDataUnsafe или неподтверждённому email. Последний способ входа
и identity linking нельзя добавлять через «просто поменять subject» в таблице.

Миграции — новые файлы, не create_all на startup. Credentials после row lock читаются
свежим SQL snapshot, не старым JOIN. Unit SQLite не доказывает PostgreSQL locking.
Реальные SMTP/API calls, production, роли и ключи не входят в AUTH-002 email-scope.
После малой правки — профильный test; полный CI перед приёмкой. Не ослаблять tests,
не обновлять зависимости и не расширять область ради скрытия ошибок. Изменённый API
экспортировать из кода. Самопроверка не независимый security review.

API-001 / внешние AI: `izo/providers/<provider>/` владеет сетевым протоколом и worker-only
секретами; `jobs/` владеет admission/lease/receipt, `media/` — файлами, `credits/` — баллами.
API/UI не получают provider key. Любой live provider по умолчанию выключен; model/price/
capabilities задаются оператором и снимаются в execution snapshot до job. Сетевой timeout
после dispatch не означает «не выполнено»: не делать автоматический платный retry и не
освобождать резерв без reconciliation. Ближайший OpenRouter test —
`tests/test_openrouter_provider.py`; реальный ключ запрещён в unit/CI/artifacts.
