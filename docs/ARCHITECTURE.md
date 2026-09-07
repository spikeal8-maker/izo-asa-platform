# Foundation 0: границы новой платформы

## Решение

Новый код, новые аккаунты. Позже — ручные компенсационные начисления через ledger
с причиной и idempotency key; старую базу не импортируем. Код и runtime не связаны
с работающим сайтом. Первый стенд локальный, production по умолчанию запрещён.

Один backend с независимыми модулями и впоследствии worker-процессами; не набор
микросервисов. Не создаём заранее пустые пакеты для всех будущих функций.
UI один для компьютера, планшета, телефона и оболочек мессенджеров.

## Что реализовано в этом PR

- Factory FastAPI без соединений и миграций на импорте.
- Liveness отдельно от проверок PostgreSQL schema revision и S3 bucket.
- Alembic baseline 0001, запускаемый отдельным migrate-контейнером.
- S3Store, приватные object keys, отдельный storage volume.
- JobSpec / Capability / AssetRef и чистая transition/routing policy.
- React shell, platform hint, safe-area CSS, темы, диалог и единый HTTP-клиент.
- OpenAPI export и TypeScript-типы из него, не вручную продублированный DTO.

Это **контракты**, а не уже работающая durable queue. Нет задания, которое
действительно можно отправить, нет прав пользователей и нет платежей.

## Следующие доменные границы

Auth/Accounts: единственная доверенная серверная сессия. Telegram и MAX проверяются
на сервере по подписанным данным, сроку действия и защите от повторов, затем
связываются с тем же аккаунтом. Не доверять platform hint текущей оболочки.

Credits: целочисленные единицы, журнал операций, reserve/settle/release, уникальный
ключ операции. Покупка и административное начисление — разные авторизованные
команды; не предоставлять обычному пользователю универсальный grantCredits.

Generation: долговечные jobs/attempts, lease, heartbeat, fencing token, ограниченные
повторы. Принятый провайдером запрос с неизвестным результатом — reconciling.
Повторять платную операцию вслепую запрещено. Chat streaming имеет собственный
request lifecycle; длительные chat tools запускают стандартные generation jobs.

Providers: реестр возможностей не делает APIs одинаковыми. Adapters явно описывают
поддерживаемые входы, выходы, streaming/polling, cancellation и cost accounting.
Credentials только server-side. Никаких fallback local -> paid без согласия.

Media/Gallery: приватные оригиналы, owned metadata и версии производных файлов.
Медиа не становятся публичными из-за известного URL. Feed publication ссылается
на asset, но может иметь отдельную публичную производную копию и собственный
жизненный цикл модерации/удаления. Бакет и оригиналы не публиковать целиком.

Local worker: исходящее HTTPS, ограниченный worker token, allowlist capabilities,
временные URL на конкретные assets. Без доступа к БД и произвольного выполнения
Python/shell/workflows из пользовательского запроса. Сейчас агента ещё нет.

Admin: серверные permissions и audit, те же доменные службы, не второй backend.
Пустая страница /admin сейчас не содержит административных API или данных.

## Storage choice

S3 protocol сохраняется независимо от поставщика. В dev выбран SeaweedFS 4.29
(single-node mini), не MinIO Community: официальный MinIO repository archived
25 апреля 2026 и заявляет прекращение поддержки. Production object storage,
backup/restore, политики retention и URLs выбираются отдельным этапом.

Источники проверки 2026-09-07:
- https://github.com/minio/minio
- https://github.com/seaweedfs/seaweedfs/tree/4.29
- https://docs.docker.com/compose/how-tos/startup-order/
- https://fastapi.tiangolo.com/deployment/docker/
- https://playwright.dev/docs/emulation

## Чего не гарантирует этот фундамент

Лимиты и import checks обнаруживают часть нарушений, но не делают архитектуру
неразрушимой. Screenshot/viewport-тесты не заменяют реальный iPhone/Android,
проверку клавиатуры, загрузок и SDK внутри Telegram/MAX. Image rollback не
откатывает БД. Volumes не являются backup. Публичный код технически можно скопировать.
