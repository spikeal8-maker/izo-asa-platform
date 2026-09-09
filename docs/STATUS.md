# Фактическое состояние IZO ASA

## ADMIN-001 · минимальная рабочая админка, 9 сентября 2026

База 1aba446b8b91752aeacd62f8291f851507d4cf14 (ENTITLEMENT-001, PR #9).
Новая ветка admin/users-compensation. Main/прошлые ветки/старый сайт не меняются.
Никаких настоящих AI/писем/платежей, пользователей, keys, GPU или deployment.

Добавлены typed staff API и интерфейс поиска/карточки пользователя, чтения баланса,
подтверждения компенсации с текущим паролем и ограниченного административного
журнала; /account/credits показывает настоящий собственный ledger вместо mock.
Это не подключает DEMO-генератор/галерею к настоящим средствам.

Начисление использует существующий CreditService.grant, общий Account/session,
конечную per-operation policy, business case и одну транзакцию с audit. Права,
состояние, verified identity, пароль/сессия повторно проверяются после KDF.
Нет самостоятельного admin signup, wallet SQL в модуле админки, роли по плану,
скрытой новой платной генерации или прямого secret editor.

Общий origin/body limit вынесен из Accounts в http_security без смены алгоритма;
тот же guard применяется к auth/admin. Validation ошибок admin не отражает пароль.
Новая миграция 0006_admin: конечный cap оператора и append-only admin_events.
CLI первичного назначения требует явной isolated dev/test среды и existing verified
аккаунта. В этом пакете не реализуется полный ACCESS-001/AD-02.

Локально проверены169 случаев (новые admin + профильные existing Credit), SQLite/ASGI,
настоящие AuthService/CreditService. Локальный FastAPI0.128.2/Alembic1.18.4 отличаются
от lock; полный целевой стек должен подтвердить GitHub. Локального Docker/полного
checkout нет: source восстановлен через fetch/прошлые архивы и сверяется по blobSHA.
OpenAPI новых routes сгенерирован и объединён с точным base без изменения старых
schemas; полный export_contracts --check обязательный этап CI.

В CI добавлены реальные PostgreSQL/HTTP before/after и прямой браузерный сценарий
через собранный web/Caddy/API/PostgreSQL. Полный итоговый SHA и выполненные проверки
фиксируются в PR/Checks после публикации. Подготовленный script не означает PASS.
Synthetic credentials сохраняются только в RUNNER_TEMP с umask077 и удаляются;
immutable journal triggers не выключаются для уборки, удаляется весь CI volume.

Scope: до30 путей, без новых dependencies, Docker/старых migrations/LICENSE, без
перерисовки всей студии. Локальные AGENTS/README дают предметный путь для правок,
нового master plan нет. Реальный расход coding-tokens неизвестен.

## Проверенная основа и ограничения

PR #9, source1aba446…: Foundation CI34299435284 (420 Python,220 browser, настоящая
PG/persistence) и security34299435148 — SUCCESS по ранее прочитанным logs. Статус
предыдущих запусков не переносится на новые изменения автоматически.

Уже есть Accounts/session, почтовая часть AUTH-002 с TEST-mail, Credits ledger,
Entitlement plans/preflight. Последний НЕ резервирует quota/jobs: admission_reserved=false.
Нет durable Jobs/Media allocator, настоящей cloud gallery, live providers/local agent,
полной админки, настоящих Telegram/MAX/SMTP, payments и production release/restore.
Изменение email/identity linking и технические gates публичного запуска ещё впереди.

Дизайн не принят; UI-viewport не доказывает реальную ОС/Mini App. Добавленный live
browser scenario должен отдельно подтвердиться, прежние220 mock cases не заменяют его.
Самопроверка не независимое security review; main protection не настраивается здесь.
PR Draft, merge/deploy не выполняются. Следующий пакет после успешной приёмки —
MEDIA-001 по NEXT, не новое проектирование основания.
