# JOBS-001: постоянные серверные задания

Реализованный ограниченный объём: текст → диагностический PNG через **test.image.v1**,
без настоящей AI-модели, платных API, пользовательских исходников, живых уведомлений
и интерфейса студии. Используются существующие Accounts, Credits, Entitlements и Media.

## Путь запроса

POST `/api/v1/jobs/quotes`: capability_id=test.image.v1, prompt, width, height.
Размер 32…512 по каждой стороне, дополнительно разрешён текущим планом. Цена тестового
адаптера — 1 тестовый балл, quote действует 120 секунд. Это не коммерческий тариф.
POST `/api/v1/jobs`: quote_id + operation_id. Никакие owner/цены/URL/ключи не принимаются.
GET `/api/v1/jobs` (limit/offset), GET `/api/v1/jobs/{id}` и POST `/api/v1/jobs/{id}/cancel`.
Успех содержит asset_id: обычные Media API выдают его и проверяют право скачивания.

Валидная quote ещё не резервирует средства. При submit сервер под Account-lock
повторно читает effective plan, существующие активные задачи, число принятых запросов
в окне, реальные media bytes/reservations и баланс. Credit hold, output allocation,
job и queued outbox event сохраняются одной внешней транзакцией. Ошибка любого шага
откатывает все четыре изменения. Один quote порождает максимум один job; повтор того
же operation_id возвращает его даже после окончания quote. Другой quote с тем же
ключом конфликтует. Снимок плана и параметров не меняется вместе с новым тарифом.

Нулевой баланс/отключённый исполнитель не запрещают читать свои задания. Чужой ID
возвращает not_found. Logout отзывает чтение сессии, но не отменяет принятую работу.

## Исполнение и сбои

Очередь — PostgreSQL, не память процесса. Нет Redis/Celery и сетевого AI SDK.
Claim сначала блокирует Accounts, затем Job; SKIP LOCKED применяется к owner-row,
а не создаёт обратный порядок locks. Скан ограничен 64 кандидатами; строгая fairness
и высокая производительность на тысячах пользователей здесь не доказаны.

Worker создаёт attempt с возрастающим fence и lease. Start/heartbeat/seal/finish
проверяют этот fence. По умолчанию lease30s, срок задания900s, максимум3 попытки;
настройки имеют конечные bounds. Повторы после crash разрешены только для чистого
локально выполняемого **тестового** адаптера. Никакого exactly-once внешнего API.
Реальные API/local pools добавляются отдельно и не получают ложной готовности.

Отмена queued/claimed/running до seal фиксирует cancelled и освобождает деньги/место
один раз. Race с seal сериализуется: после seal файл уже мог записаться, поэтому
cancel_requested остаётся намерением, а успех и списание могут завершиться штатно.
Прекращение сессии/изменение плана не отменяет существующую финансовую обязанность.

Перед записью S3 транзакция сохраняет hash, размер и серверный object key. Затем
SQL-lock отпускается. Ответ S3 потерян — статус reconciling, резерв не освобождается.
После restart другой процесс сверяет существующий файл; asset, settlement, terminal
state и outbox завершаются атомарно. Повтор callback/finish не списывает повторно.
Reconciliation ограничена пятью чтениями с backoff; затем error_code=
reconciliation_required и durable событие для оператора. Автоматическое удаление
неизвестного объекта/освобождение его квоты или новая генерация запрещены. UI разбора
такого случая и доставка уведомлений будут отдельными функциями.

## Общий Media, не вторая галерея

Новая таблица media_output_allocations хранит резерв/кандидат результата. Готовый файл
попадает в прежнюю media_assets. Forward-migration0008 добавляет явную пару upload_id /
output_id с XOR и composite ownership FK. Старые assets сохраняют ID, object key,
hash и привязку upload. Для результата не создаётся фиктивная пользовательская загрузка.
Общая usage-сумма учитывает upload и job-output reservations, предотвращая их гонку.
Старые migrations не редактируются. SQLite-миграция проверяется отдельно; её блокировки
не считаются доказательством PostgreSQL. До будущего production-upgrade нужен backup
и проверка миграции с соответствующим объёмом старых данных.

## Запуск только в изолированном dev/test

Настроить существующий стенд по корневому README, аккаунт/план и тестовое начисление
операторскими сценариями. Public signup не выдаёт plans.write или бесплатный баланс.
По умолчанию `IZO_JOBS_ENABLED=false`. Для локального тестового Compose записать
`IZO_JOBS_ENABLED=true` в локальную конфигурацию, не коммитить секреты. Затем:

```sh
docker compose up --build --wait
docker compose --profile jobs up --build job-worker
```

Один проход без постоянного worker:

```sh
docker compose run --rm api python -m izo.jobs.worker --once
```

Worker работает foreground и штатно прекращает новый приём после SIGTERM/SIGINT,
давая ограниченной текущей операции завершиться. Это серверный API-worker с доверенным
DB-доступом. Домашний исполнитель по HTTPS в этот пакет не входит. Здесь нет production
режима, подключения GPU и расходов внешнего провайдера.

## Проверка и экономность

```sh
python -m pytest tests/test_jobs.py tests/test_jobs_recovery.py tests/test_jobs_http.py tests/test_jobs_migration.py tests/test_jobs_boundaries.py
python -m pytest tests/test_media.py tests/test_media_access.py tests/test_media_migration.py
python tools/export_contracts.py --check
```

CI выполняет `tools/jobs_acceptance.py before/after` на PostgreSQL/S3 и запускает
настоящий отдельный worker-process; между фазами Compose down/up. Проверяются общий
admission, два submit/claim, конкуренция job/upload за одно место, неудачная задача,
известный сохранённый S3-результат с потерянным ответом, stale fence, persistence и
сверка общего Credit ledger. Это HTTP-сценарий без новой пользовательской страницы.

Job outbox содержит только job ID/event type/time; уведомления здесь не отправляются.
Два workflow проверяют все PR независимо от базовой ветки, сохраняя read-only token и
запрет high/critical npm-проблем. Это не branch protection и не независимый review.

Опорные механизмы: PostgreSQL explicit locking
https://www.postgresql.org/docs/17/explicit-locking.html
и SQLAlchemy transactions
https://docs.sqlalchemy.org/en/20/core/connections.html#using-transactions
Проверены 2026-09-09; конкретные ограничения выше — проектные решения этого этапа.
