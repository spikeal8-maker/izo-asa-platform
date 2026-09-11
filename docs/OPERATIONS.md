# Эксплуатация и выпуск IZO ASA · спецификация 0.1

**Текущий Compose — изолированный dev/test, не инструкция публичного production-развёртывания.** Реальные команды существующего стенда находятся только в [README](../README.md). Не выполнять несуществующие deploy-команды из архитектурных диаграмм.

## 1. Среды

| Среда | Назначение | Данные/секреты | Разрешённые действия |
|---|---|---|---|
| Unit/UI tests | Проверка логики и взаимодействия | Fake data; сеть запрещена/заменена | Ни денег, ни настоящих сообщений |
| Compose integration | Настоящие PostgreSQL/S3/API в изоляции | Временные данные/случайные test credentials | Контролируемое пересоздание/сбой зависимостей |
| Development | Разработка нового продукта | Только отдельные dev accounts/storage | Нет подключения к старому сайту |
| Staging | Приёмка приближённого к выпуску артефакта | Отдельные accounts, tokens, DB, bucket | Реальный provider test только по разрешению/лимиту |
| Production | Реальные пользователи | Защищённые постоянные данные | Только утверждённые releases и операторские процедуры |

Нельзя делать production development-окружением через одну переменную. Старый сайт, его FRP/DNS, Windows-службы, база и GPU не меняются при разработке новой основы.

## 2. Что уже проверяет Foundation

В GitHub CI собираются web/API images, запускаются миграции и зависимости; записывается canary в PostgreSQL/S3, контейнеры пересоздаются без удаления volumes и canary читается снова. Остановка storage проверяет различие API liveness/готовности. Это не backup/restore rehearsal и не проверка пользовательской генерации.

Unit/CI остаются изолированными от реального AI spend. Канонический fal worker уже имеет внешний adapter contract, но live key/provider billing не считаются принятыми только из-за наличия ключа. Внешний egress разрешается только provider worker в явно настроенной среде; PostgreSQL/S3 ради AI в интернет не открываются.

## 3. Production-топология — целевое решение

Для первого сервера: HTTPS edge, immutable web/API images, отдельный worker-процесс, PostgreSQL и S3-compatible storage. Managed или self-hosted БД/storage выбираются оператором отдельно. Kubernetes и большое количество микросервисов не требуются для первого выпуска.

API и workers используют общее версионированное приложение, но роли процесса раздельны. Несколько API-процессов допустимы только после проверки отсутствия дублирующихся startup workers/миграций. DB migration выполняет один owner, не каждый процесс при старте.

У local GPU-agent своё обновление и protocol version. Он подключается исходящим HTTPS, не является общедоступной ComfyUI-службой. Его outage не блокирует API-core, кроме задач, явно выбравших local execution.

## 4. Секреты и сеть

Ключи не входят в Git, Docker image, frontend bundle, prompts, скриншоты, stdout и CI artifacts. Production secret source выбирается отдельным пакетом: secret files/manager с ограниченными правами. Environment допустимо только при соответствующей политике доступа/логирования; значение не печатается.

Ввод ключа в админке — write-only, чтение возвращает masked metadata. Rotation/revocation имеют audit; доступ ограничен provider/role. Локальный worker получает только scoped worker token, не root credentials БД/storage. После утечки требуется отзыв/ротация, а не только удаление строки из последнего коммита.

HTTPS обязателен для production/session/Mini Apps. Доверенные proxies и forwarded headers задаются явно; нельзя доверять любому X-Forwarded-For. Public API, private service network и local worker ingress разделяются. Signed upload/download URLs ограничены по сроку и объекту.

## 5. Выпуск и откат

Целевой порядок: принять PR → build один раз из exact SHA с lockfiles/digests → проверить тот же артефакт на staging → проверить совместимость схемы/backup → применить разрешённый release → smoke/version → подтвердить сценарии.

Production использует code из image, не изменяемую bind-mounted Git-папку. В версии фиксируются commit, image digest и schema revision. Frontend/API version mismatch обнаруживается, не скрывается HTTP 200.

Перед изменениями схемы: expand/contract где возможно, без разрушительного удаления в обычном feature PR. Откат image не откатывает данные. Если старый код не совместим с новой схемой, простой возврат тега запрещён; нужен заранее проверенный rollback/forward-fix план.

Blue/green не является обязательным Foundation; с одной БД и workers сначала нужен безопасный контролируемый выпуск с drain. Внешние job references, резервы и outbox переживают restart; нельзя обнулять их для чистого запуска.

## 6. Резервные копии и восстановление

Named volume защищает от пересоздания контейнера, не от удаления volume, сбоя диска, взлома или ошибочной миграции. Запрещено использовать down -v/prune с нужными данными в обычных инструкциях выпуска.

До публичного запуска определить RPO (сколько данных допустимо потерять) и RTO (допустимое время восстановления). Никакие численные значения здесь не считаются принятыми владельцем. Нужны PostgreSQL backup с проверяемой согласованностью, backup/versioning blobs, защищённые secrets recovery и копия вне единственного сервера.

Rehearsal: восстановить в отдельное окружение, проверить DB revision/counts, соответствие metadata/object hashes, владельцев, sample media и balances/reservations. Не включать реальные bot delivery/provider retries до проверки, чтобы восстановление не повторило платные операции. Зафиксировать фактическую длительность и результат. Копия «есть где-то на диске» не является доказательством восстановления.

## 7. Наблюдаемость и инциденты

Отдельно: HTTP liveness; readiness БД/schema/storage; worker lease/heartbeat и свежесть успешной работы; capability/provider availability. Отсутствие необязательной GPU-модели — деградация capability, не падение всей платформы.

Минимальные метрики: error rate, latency, oldest queued age, running/reconciling age, retries, upload failures, balance anomalies, storage usage и provider spend. Алерты имеют порог, owner и инструкцию; пустая очередь не считается unhealthy только из-за отсутствия новых success.

Incident first response: зафиксировать version и safe request/job IDs; остановить новые расходы проблемного provider/pool, если нужно; сохранить evidence; выяснить было ли внешнее действие; выполнить bounded recovery. Не запускать бесконечные restarts и не повторять платную работу из-за отсутствующего UI-ответа.

Логи структурированные, redacted. Prompts/личные файлы не записываются полностью по умолчанию. Доступ к данным для разбора ограничен целью и audit. Политики retention, удаления аккаунтов, обработки обращений и допустимой аналитики утверждаются до публичного выпуска.

## 8. Gate публичного перезапуска

Обязательны: утверждённый UX; рабочие signup/login/recovery; private media access; credits/job idempotency; хотя бы один реальный заявленный provider; реальные Telegram/MAX сценарии, если они объявлены; выбранные licence/terms/privacy; moderation/reporting до public feed; нагрузочный baseline; alerts; backup restore; безопасный release/rollback; понятное сообщение о новой регистрации и компенсациях.

Рабочий сайт переключается только по отдельному разрешению владельца. Закрытая alpha может иметь меньший scope, но не должна изображать полный готовый продукт. Реальные payments не включаются без отдельной проверенной интеграции и применимых требований; юридические вопросы проверяются для выбранных стран/оператора специалистом.

Источники, проверены 2026-09-07:
- Docker Compose production: https://docs.docker.com/compose/how-tos/production/
- Docker volumes: https://docs.docker.com/engine/storage/volumes/
- Telegram Mini Apps: https://core.telegram.org/bots/webapps
- MAX validation: https://dev.max.ru/docs/webapps/validation
