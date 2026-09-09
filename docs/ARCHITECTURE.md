# Архитектура IZO ASA · спецификация 0.1

Это карта действующего основания и целевых границ. **Существующий код и предлагаемые сущности различаются явно.** Продуктовые сценарии — [PRODUCT](PRODUCT.md); runtime — [AI_RUNTIME](AI_RUNTIME.md); реализация — [NEXT](NEXT.md).

## 1. Принятый подход

Новая реализация без импорта старого кода/БД. Один modular monolith на FastAPI с отдельными worker-процессами по мере появления задач; единый React/TypeScript UI. PostgreSQL хранит транзакционные данные; S3 boundary хранит файлы. Docker обеспечивает воспроизводимый runtime, но не гарантирует качество архитектуры.

API-core не зависит от наличия GPU дома. Локальный исполнитель подключается исходящим HTTPS и не получает доступ к PostgreSQL. Внешние API вызываются только серверным адаптером. Общие contracts не превращают разные providers в одинаковые сервисы.

## 2. Реальная карта Foundation

| Файл/область | Что уже есть | Чего пока нет |
|---|---|---|
| `apps/api/izo/app.py` | FastAPI factory и health/API shell | Продуктовые routes и авторизация |
| `apps/api/izo/config.py` | Конфигурация foundation-стенда | Production secrets manager |
| `apps/api/izo/contracts.py` | Modality, Executor, Capability, JobSpec, AssetRef | Public create-job API и полный model registry |
| `apps/api/izo/generation.py` | Чистые правила routing/state | Персистентная очередь и реальный worker |
| `apps/api/izo/health.py` | Проверки готовности зависимостей | Полный operational dashboard |
| `apps/api/izo/storage.py` | Приватный S3 boundary | Пользовательская загрузка и проверка ownership |
| `apps/api/migrations` | Alembic baseline | Пользователи, ledger, jobs и публикации |
| `apps/web/src/shell` | Общая техническая оболочка | Утверждённый дизайн и продуктовые screens |
| `apps/web/src/platform` | Presentation hint платформы | Доверенная Telegram/MAX identity |
| `packages/contracts` | Экспорт OpenAPI | Отдельная схема каждого будущего домена |
| `tests`, `apps/web/e2e` | Unit/architecture и browser shell tests | E2E реальной генерации и пользовательских прав |

Не объявлять файл `contracts.py` полной схемой продукта. JobSpec уже помечен internal server-owned: frontend не должен присылать owner, reserved_credits, provider endpoint или credentials как доверенные значения.

## 3. Целевые модули и владельцы данных

| Модуль | Владеет | Общается с другими через |
|---|---|---|
| Accounts | Аккаунты, auth identities, credentials, sessions, permissions | Доверенный Principal, команды session/permission |
| Credits | Счёт, проводки, резервы, тарифные правила | reserve/settle/release/grant с авторизацией и operation ID |
| Catalog | Providers, capabilities, model versions, разрешения/цены | Версионированный снимок доступной модели |
| Generation | Jobs, attempts, dispatch, lease, recovery | Команды credits/media/providers и события |
| Providers | Преобразование запроса/ответа конкретного AI-сервиса | Typed result/error/progress; не прямые записи в users/ledger |
| Media | Assets, файлы, derivatives, uploads, lifecycle | Owner-checked ссылки и команды finalize/delete |
| Gallery | Пользовательское представление assets/collections | Запросы к разрешённым media; не копия файловой БД |
| Feed | Publications, reactions, reports, moderation | Ссылки на media и отдельные публичные derivatives |
| Chat | Threads, messages, requests, tool invocations | Обычные authorized generation/media commands |
| Notifications | Durable outbox, delivery attempts, preferences | События доменов; сбой доставки не отменяет успех задачи |
| Admin | Server permissions, административные routes и UI | Те же доменные команды; нет второго расчёта баланса |

Модули создаются под реализуемый сценарий, не заранее как десятки пустых каталогов. Следующие пакеты размещаются внутри `apps/api/izo/` и `apps/web/src/features/` по согласованной ответственности. Не вводить параллельные `modules/`, `contexts/`, `services-v2/` с той же логикой.

Направление зависимостей: presentation/routes → application services → domain contracts; infrastructure реализует interfaces и подключается в composition root. Междоменные commands orchestration допустимы; импорт приватных ORM-моделей чужого домена и произвольный SQL в UI/routes — нет. На первом этапе допускается один transaction/unit-of-work в общем процессе вместо распределённой транзакции.

## 4. Целевая модель данных

Ниже — логическая модель для будущих migrations, не уже созданные таблицы. Каждый пакет добавляет точные столбцы, FK, constraints, индексы и API-схемы, необходимые его сценарию.

| Сущность | Связи и обязательные инварианты |
|---|---|
| Account | Неизменяемый ID, public code, display name, status; auth-поля не смешиваются со всей историей |
| AuthIdentity | Account + provider + subject; уникальность provider/subject; связь подтверждена сервером |
| Session | Account, hash opaque token, срок, отзыв, устройство/платформа; не хранить открытый session token |
| PermissionGrant | Кто выдал, кому, scope, когда; public register не назначает staff |
| CreditAccount | Владелец, projection баланса/версии; изменение только с проводкой в одной транзакции |
| LedgerEntry | Целочисленные единицы, тип/основание, immutable operation ID; correction новой записью |
| CreditReservation | Job/request, сумма, состояние; один резерв на логическую операцию |
| CapabilityVersion | Modality, input/output/limits, provider/model, executor, schema/pricing versions, visibility |
| Job | Owner, intent/params snapshot, idempotency key + request hash, status/version, reserve, timestamps |
| Attempt | Job, номер, executor, fencing token/lease, provider reference, outcome; попытка не новая покупка |
| Asset | Owner, kind, object key, mime/size/hash, status, creation/source links; оригинал private |
| AssetDerivative | Asset + назначение/версия; preview и public copy имеют отдельный lifecycle |
| Upload | Владелец, ожидаемый тип/размер, одноразовая финализация, срок; не готовый asset до проверки |
| Publication | Автор, asset reference, выбранные публичные поля, moderation, status; не переключатель всего bucket |
| ChatThread/Message | Owner, упорядоченная история, asset references; чужая история недоступна |
| ChatRequest/ToolInvocation | Idempotency, budget, tool schema, confirmation, связанный Job; audit без secrets |
| OutboxEvent | Domain event + delivery status/attempt; at-least-once с idempotent consumer |
| AuditEvent | Actor/action/target/reason/time/request; PII и secrets минимизированы |

Доступ проверяется при чтении и записи, в том числе по связанным объектам. UUID или opaque object key не заменяют ownership. Все внешние идентификаторы имеют namespace провайдера; нельзя по слову `openrouter` решить, что задача обязательно является видео.

## 5. Транзакции и учёт баллов

Предлагаемая схема счёта: доступно = зачислено − окончательно списано − активные резервы. Резерв не является вторым окончательным списанием. Поле-проекция допустимо ради производительности, но сверяется с журналом и обновляется атомарно. Денежные суммы провайдера хранятся decimal/minor units, баллы — целочисленно; float для итогового расчёта запрещён.

Создание job, резерв и запись события dispatch выполняются одной транзакцией. При недостатке средств job не отправляется. Конкурентный резерв проверяет доступный остаток под транзакционной защитой; два запроса не могут потратить один остаток.

Завершение: после валидации результата регистрируется asset, фиксируется конечное состояние и settlement, создаётся outbox-event. S3 и PostgreSQL не составляют одну ACID-транзакцию: сначала временный объект, потом подтверждение metadata/финализация с идемпотентным reconciliation и очисткой orphan objects. Сбой после upload не должен вызывать повторную платную генерацию.

Превышение provider cost над подтверждённым максимумом нельзя незаметно списать с пользователя. Сначала фиксируется политика: ограничить расход, отдельно спросить доплату либо принять превышение на стороне сервиса. Возврат баллов пользователю и возврат денег внешним провайдером — не одно и то же.

## 6. Задания и параллелизм

PostgreSQL — durable source of truth. Для первого worker допустим bounded polling/transactional claim без Redis/Celery/Kafka. Выбор конкретной locking-схемы доказывается конкуретными тестами; in-memory queue используется только для wake-up.

Pools минимум разделяют API и local GPU; конкурентность/лимиты дополнительно задаются provider/model/resource. Не держать DB transaction открытой на всё время сетевой генерации. Heartbeat/lease продлеваются отдельно, старый fencing token не может завершить переприсвоенную работу.

At-least-once execution и idempotent terminal transitions — цель. Exactly-once внешнего платного вызова не обещается. Неизвестный outcome уходит в reconciling; полный алгоритм в AI_RUNTIME.

## 7. HTTP, контракты и безопасность

OpenAPI генерируется из backend; frontend использует один transport и generated types. Продуктовые публичные запросы отделяются от internal JobSpec. Обязательные категории ошибок: validation, unauthenticated, forbidden, insufficient credits, unavailable capability, conflict/idempotency mismatch, rate limited, provider failure, reconciling. Точные HTTP-коды/DTO фиксируются тестами при введении endpoint, не разбросаны по компонентам.

Типовая безопасная ошибка содержит публичный code/message/request ID и retryability, не stack trace/ключ/внутренний адрес. Статус и progress читаются с owner check; streaming/events не обходят session и не открывают чужие jobs.

Auth: HttpOnly server session, HTTPS/Secure в production, CSRF/Origin policy для мутаций, throttling, password hashing через проверенную библиотеку, восстановление и отзыв сессий. Параметры сроков/лимитов определяются в AUTH-001. Mini App SDK/алгоритмы проверяются по актуальным официальным материалам, не копируются по аналогии между платформами.

Files: лимиты размера/типа/разрешения/длительности, content sniffing, safe decoder, quarantine и проверка owner. Пользовательский URL не становится произвольным server fetch; запрещены metadata/private-network endpoints и unsafe redirects. Local provider endpoints — отдельный доверенный канал, не исключение для пользовательского SSRF.

## 8. Storage и публикации

В foundation dev используется SeaweedFS через S3. Production storage выбирается отдельно без изменения модели владения. Файлы не хранятся в Git/image контейнера; metadata и checksum — в БД, blobs — в storage. Volume устойчив к пересозданию контейнера, но не является backup.

Подписанный URL имеет короткий срок, ограниченный object/method и выдаётся только после permission check. Он может действовать до истечения срока после отзыва права; для более строгого отзыва нужен mediated download. Журнал и аналитика не сохраняют полный signed URL.

Feed может использовать отдельную публичную производную копию; удаление публикации, оригинала и preview — связанные, но разные операции. Публикация не раскрывает исходные references/prompt. 3D manifest не ссылается на произвольные внешние скрипты, материалы проходят проверку.

## 9. Развитие без ложных гарантий

Добавление модели с уже поддержанными inputs/outputs обычно ограничивается adapter/config/tests. Новая modality, сложный редактор, streaming или нестандартный result требуют расширения схемы и UI. Capability registry не заменяет инженерную работу.

Сейчас лимиты/import tests защищают несколько конкретных файлов; они не проверяют все будущие модульные границы. При выделении нового домена добавляется профильный тест. Не увеличивать limits и не дробить файл на бессмысленные куски ради формального зелёного статуса.

Источники и опорные реализации, проверены 2026-09-07:
- PostgreSQL transaction locks: https://www.postgresql.org/docs/current/explicit-locking.html
- OWASP sessions: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Telegram signed data: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
- MAX validation: https://dev.max.ru/docs/webapps/validation
- Docker volumes: https://docs.docker.com/engine/storage/volumes/
