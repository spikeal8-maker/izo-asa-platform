# План реализации IZO ASA · версия 0.1

Это единственный план работ. Реальная готовность хранится в [STATUS](STATUS.md). Ни одна строка со статусом «план» не является поручением немедленно реализовать весь продукт. Правила постановки задачи — [DEVELOPMENT](DEVELOPMENT.md).

## 1. Что делать сейчас

Технический Foundation 0 существует в PR #1 и прошёл свой CI, но не объединён в main и не прошёл отдельную приёмку. Полноценная продуктовая спецификация добавляется документационным пакетом DOC-001. Текущий визуал владельцем не принят.

Порядок ближайших действий: проверить Foundation/diff/документацию → принять безопасную техническую основу → выполнить **UX-001** → утвердить визуальное направление → строить AUTH-001 и первый image flow. Backend-задачи, не зависящие от дизайна, допускаются после принятия foundation отдельным scope; не запускать нескольких пишущих агентов в одних файлах.

Следующий результат для владельца — не ещё один абстрактный фундамент, а интерактивно проверяемые студия, результат и галерея. Пока это прототип, он прямо так обозначается.

## 2. Полная последовательность и зависимости

| ID | Результат | Зависит от | Главная проверка | Соответствие продукту |
|---|---|---|---|---|
| DOC-001 | Единая спецификация, admin/UX/runtime/план и фактический статус | Foundation source | Только документация; нет ложных claims | P-01…P-12 |
| F0-ACCEPT | Review и принятие каркаса; решение о branch protection | PR #1 + DOC-001 | Exact-SHA checks, границы, отсутствие secrets | Основа |
| UX-001 | Интерактивный прототип image/result/gallery | F0-ACCEPT, UX | Владелец принимает mobile/tablet/desktop | P-02/P-07 |
| AUTH-001 | Web аккаунт/session/logout/permissions skeleton | F0-ACCEPT | Forgery, CSRF, expiry, revoke, rate limit | P-01/P-12 |
| AUTH-002 | Подтверждение адреса/восстановление/связывание identity | AUTH-001 | Fake mail, replay, double-link, account isolation | P-01/P-12 |
| CREDIT-001 | Журнал, резерв/списание/освобождение | AUTH-001 | Конкурентный расход не уводит ниже допустимого остатка | P-09 |
| ADMIN-001 | Ограниченная карточка пользователя + компенсация | AUTH-001, CREDIT-001, UX tokens | Permission + одна проводка на заявку + audit | P-10/P-09 |
| MEDIA-001 | Owner-scoped assets, upload/finalize/private download | AUTH-001 | MIME/size, чужой ID, expired URL, S3 failure | P-07 |
| JOBS-001 | Durable job/attempt, worker, lease/recovery, fake provider | CREDIT-001, MEDIA-001 | Restart, duplicate, cancel, stale lease, bad-job isolation | P-02…P-05 |
| IMAGE-001 | Первый сквозной image flow и галерея | UX-001, AUTH, ADMIN-001, JOBS-001 | Browser → API → worker → S3 → gallery | P-02/P-07 |
| CHANGE-001 | Проверка стоимости трёх обычных изменений | IMAGE-001 | Изолированный scope и фактические расходы агента | Управляемость |
| API-001 | Один реальный AI provider/модель | IMAGE-001, выбранный provider/бюджет | Разрешённый реальный result + settlement + errors | P-02 |
| CATALOG-001 | Админский registry моделей/версионность/credentials | API-001, ADMIN-001 | Disabled candidate, публикация, no key leakage | P-10 |
| LOCAL-001 | Agent на GPU-ПК, outbound protocol, отдельный pool | JOBS-001, API-001, CATALOG-001 | GPU outage не останавливает API | P-02/local |
| PLATFORM-001 | Telegram adapter и signed login | AUTH-002, стабильный image flow | Реальный клиент + forged/expired initData negative tests | P-01 |
| PLATFORM-002 | MAX adapter и signed login | AUTH-002, стабильный image flow | Реальный MAX + проверка официального алгоритма | P-01 |
| FEED-001 | Публикация, чтение, снятие, жалоба/модерация | MEDIA-001, ADMIN-001, IMAGE-001 | Private original не раскрыт; снятие закрывает выдачу | P-08/P-10 |
| CHAT-001 | Streaming text, история, image tool | AUTH, CREDIT, IMAGE, API | Budget, tool rights, duplicate, disconnect, injection | P-06 |
| VIDEO-001 | Один video capability + viewer/галерея | JOBS, MEDIA, API, утверждённый UX | Poll/reconcile, cancel cost, duration, сохранность | P-03 |
| AUDIO-001 | Одна audio capability, затем ASR/TTS/music отдельно | JOBS, MEDIA, API | Permission mic, player, безопасный файл и cost | P-04 |
| THREE-D-001 | Один 3D capability + manifest/viewer/download | JOBS, MEDIA, API | Safe resources, формат, memory budget, preview fallback | P-05 |
| NOTIFY-001 | Durable inbox, потом bot/mail delivery | AUTH, JOBS, preferences | Дубликат/сбой доставки не повторяет генерацию | P-11 |
| OPS-001 | Staging, alerts, secrets, backup/restore, release | Стабильный ограниченный продукт | Restore в отдельную среду, exact artifact, rollback | Надёжность |
| BILLING-001 | Оплата/тарифы — отдельный разрешённый этап | CREDIT, ADMIN, юридические/провайдерские решения | Verified provider event, idempotency, refund/reconcile | P-09 |
| LAUNCH-001 | Публичный перезапуск заявленного scope | Принятые включённые функции + OPS + safety gates | Никаких обещанных неработающих разделов | Релиз |

Это порядок по зависимостям, не календарная оценка и не требование ждать 3D ради закрытой image-alpha. После API/LOCAL можно изменить порядок Feed/Chat/Video/Audio/3D по решению владельца без переделки общего foundation. Telegram/MAX и безопасность обязательны до запуска, если Mini Apps входят в публичное обещание. Реальные payments включаются только когда отдельно готовы.

## 3. Карточки ближайших пакетов

### F0-ACCEPT — не добавлять продуктовые функции

Результат: проверенная отправная точка. Scope: review существующего PR, состояние CI, dependency locks, реальные команды, licence/status без изменения лицензии. Отдельно проверить security-sensitive конфигурацию и фактическую доступность branch protection.

Приёмка: понятно, какие tests действительно запускались; нет production/GPU зависимости; отмечены limits проверок. Merge не означает deploy. Продуктовая спецификация и дизайн принимаются отдельно. Найденные критические дефекты исправляются ограниченными пакетами, не широким переписыванием foundation.

### UX-001 — ближайшая пользовательская задача

Вход: UX и PRODUCT P-02/P-07, отрицательная оценка текущего оформления. Результат: одна качественная концепция, работающая навигация image → result → gallery, состояния error/loading, примеры адаптации на трёх типах устройств.

Scope: `apps/web/src/shell/`, новые связные UI-components/features под этот прототип, e2e и соответствующая документация. Новые каталоги создаются только если нужен реальный компонент. Не входят backend, SQL, credits, providers, CI, Docker, реальная генерация и полная админка.

Evidence: интерактивный просмотр, screenshots с viewport, keyboard/touch/overflow tests, перечень fake data. Владелец принимает внешний вид; зелёный CI этого не заменяет. При отказе меняется концепция, а не разводятся несколько параллельных версий UI.

### AUTH-001 — надёжная единая identity

Вход: Accounts/security из ARCHITECTURE и PRODUCT P-01. Scope: новый accounts domain в `apps/api/izo/`, необходимые migration/API/UI/test, без generation и оплаты. Сразу один immutable account ID, credential/session отдельно, default user role. Для публичного использования нужны AUTH-002 и разрешённая доставка.

Evidence: регистрация/вход/выход на изолированной базе, безопасное хранение пароля/session, отказ forged identity, CSRF/rate limit, отзыв/expiry, запрет role escalation. API-схема генерируется и используется UI. Settings по session TTL и policy документируются в том же пакете.

### CREDIT-001 + ADMIN-001 — два отдельных PR

CREDIT создаёт целочисленный ledger и reservation model с атомарными командами, без денег. ADMIN добавляет только разрешённое начисление по заявке и минимальную карточку пользователя. Не строить полную CRM прежде первого результата.

Evidence: двойное/конкурентное подтверждение, insufficient funds, reserve/settle/release, отказ без permission, audit и компенсация ошибки новой проводкой. Пользовательский экран показывает доступные/зарезервированные баллы и историю.

### MEDIA-001 + JOBS-001 — также отдельные PR

MEDIA: загрузка/проверка/finalize/private access. JOBS: durable lifecycle поверх этих assets и credits. Fake provider детерминированно возвращает тестовый результат; fake mode не включается в production по умолчанию.

Evidence: restart API/worker, bad job isolation, concurrency, lease expiry, stale result, S3 failure после внешнего результата, unknown outcome. Нельзя принять только unit state enum за рабочую очередь.

### IMAGE-001 — первый законченный продуктовый путь

На новом тестовом аккаунте: войти → получить административные баллы → выбрать fake image model → создать → увидеть состояние → открыть результат в своих работах → скачать → перезапустить контейнеры → снова увидеть результат и корректный баланс.

Второй пользователь не может прочитать работу первого. Повтор клика/HTTP request не повторяет списание. Ошибка не создаёт фальшивый успех. Evidence включает браузерные сценарии по настоящему изолированному backend, не только mock routes.

### API-001 — только один внешний adapter

Нужны отдельно выбранные provider/model, разрешённый реальный ключ, бюджет и supported modes. Добавляются adapter, controlled egress, catalogue configuration и contract/error tests. Не вводить много ключей, пять модальностей и fallback chain одновременно.

Evidence: один разрешённый end-to-end real flow; server cost/usage при доступности; безопасные ошибки и reconciliation; ключ не попал в browser/log/artifact. Наличие ключа само по себе не разрешает вызов.

## 4. Сквозные критерии качества

Каждый пакет: определён пользовательский результат, scope и non-goals; есть tests на ошибки, которые он вводит; docs/schema синхронны; exact SHA и evidence сохранены; явно сказано, что не реализовано. Для UI — affected devices, для денег/identity — отдельный review, для внешнего действия — разрешение.

Нельзя принимать весь foundation по числу тестов, а дизайн по отсутствию TypeScript ошибок. Нельзя объявлять «все модальности поддержаны» по наличию enum. Нельзя считать production готовым по одной успешной Compose-сборке.

## 5. Что требуется решить владельцу, а что решает разработчик

До UX-001: владелец оценивает предложенную концепцию; техническую структуру компонентов выбирает разработчик. До API-001: модель/provider и максимальный расход. До публичного запуска: состав обещанных функций, цены/квоты, правила отмены/превышения, retention/privacy/moderation, licence и оператор/хостинг.

Технологические детали внутри принятых ограничений не требуют постоянных вопросов владельцу. Нельзя молча принимать за него денежные, правовые и продуктовые обещания. Нерешённые вопросы не блокируют бесплатный UI/fake development, если не затронуты его контракты.
