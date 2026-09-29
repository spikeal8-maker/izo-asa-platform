# План реализации IZO ASA · версия 0.2

Единственный порядок пакетов; факты — [STATUS](STATUS.md). Пакет не равен готовой функции и не является командой немедленно реализовать весь реестр. U/D принадлежат [PRODUCT](PRODUCT.md), A/AD/S — [ADMIN](ADMIN.md). Правила процесса — [DEVELOPMENT](DEVELOPMENT.md).

## 1. Ближайшая последовательность

DOC-003 закрывает документальные пробелы: страницы, действия, доступ и типизированные настройки. После проверки этого пакета не создавать ещё один «генеральный план». Следующий шаг — F0-ACCEPT, затем один интерактивный UX-001 с отдельной визуальной приёмкой, затем ограниченный image flow. Продуктовая спецификация v0.2 не утверждает окончательные цены/дизайн и не разрешает production.

Backend-пакеты, не зависящие от оформления, допустимы после F0-ACCEPT отдельными scopes. Один пишущий агент на пересекающиеся файлы. Нельзя превращать реестр экранов в обязательство сначала построить весь settings engine, всю админку и все модальности.

## 2. Пакеты, зависимости и связь с реестрами

Зависимость — результат уже принятого пакета, не просто наличие issue. Ранее описанные DOC-001/DOC-002 — история, DOC-003 — текущее уточнение. Все будущие пакеты в таблице имеют статус ПЛАН, если STATUS не доказывает иное.

| ID | Результат / основные U/A/S | Зависит от | Критерий завершения |
|---|---|---|---|
| DOC-001 | Спецификация продукта 0.1 | Foundation source | Разделены требования и реализация |
| DOC-002 | Agent rules, credentials, QHD/4K | DOC-001 | Расширены контракты, без claims новой функциональности |
| DOC-003 | PRODUCT §11–13, ADMIN §2–11, traceability | DOC-002 | Уникальные IDs, покрытие экранов/доступа/полей/пакетов, docs-only diff |
| F0-ACCEPT | Технический review PR #1, правила приёмки/защиты main | Foundation + DOC-003 | Exact-SHA CI, отсутствие secrets/production зависимости, ограничения понятны; отдельное разрешение merge |
| UX-001 | Прототип U-09/U-10/U-18/U-19/U-20/U-44/U-45, D-01…D-05; пример A-03 | F0-ACCEPT | Одна принятая концепция, настоящий UI на fake data, QHD/4K/HiDPI; не real AI |
| AUTH-001 | U-02/U-03/U-26, trusted sessions и basic permission model; S-01…S-08 минимально | F0-ACCEPT | Register/login/logout, CSRF, revoke, expiry, forgery/rate limits, no role escalation |
| AUTH-002 | U-04…U-06/U-25/U-27; подтверждение/recovery и linking service | AUTH-001 | Replay/expiry, нейтральное восстановление, последний метод, чужая identity; fake mail |
| CREDIT-001 | U-28/A-04; ledger/reserve/settle/release | AUTH-001 | Race/insufficient funds/idempotency, целочисленный баланс; без реальных денег |
| ENTITLEMENT-001 | PRODUCT §12, A-06/A-07, S-09…S-23 | AUTH-001, CREDIT-001 | Один basic revision, allowlists/finite quotas, zero/expired/overquota tests; extended/custom можно выключить |
| ADMIN-001 | A-02/A-03/A-05/A-29, AD-01/AD-02, S-56 | AUTH-001, CREDIT-001 | Минимальный owner scope и одно начисление на вручную заведённый case; audit; не полная CRM |
| MEDIA-001 | Private assets/uploads/download, A-17/A-18; S-15/S-16/S-50 | AUTH-001, ENTITLEMENT-001 | Owner/MIME/size/quarantine/expired URL, S3 failure; не public bucket |
| PROFILE-001 | U-24 имя/avatar/preferences | AUTH-001, MEDIA-001, UX-001 | Свой профиль, безопасный avatar, theme choice не меняет права |
| JOBS-001 | U-17/U-18/A-15/A-16, AD-06, S-42/S-43 | CREDIT-001, ENTITLEMENT-001, MEDIA-001 | Durable attempt/lease/fencing, fake provider, bad-job isolation/restart/cancel; outbox intent |
| IMAGE-001 | U-09/U-10/U-19/U-20 с настоящим изолированным backend | UX-001, AUTH-002, ADMIN-001, JOBS-001 | Вход → баллы → fake image → private S3 → gallery/download → restart; второй user denied |
| CHANGE-001 | Стоимость обычных изменений | IMAGE-001 | Три изолированные задачи: mobile button, entitlement, provider error; фактические tokens/attempts или «нет данных» |
| API-001 | Один настоящий API adapter/capability/connection | IMAGE-001, выбранные provider/бюджет | Разрешённый real result, settlement/error/reconcile, controlled egress, no leaked key |
| SETTINGS-001 | A-27/AD-08, typed policy lifecycle для используемых полей | ADMIN-001, ENTITLEMENT-001 | expectedRevision, validation/default/REQ, safe publish/audit; не все 66 групп сразу |
| CATALOG-001 | A-08…A-12, AD-03/AD-04; S-24…S-38 | API-001, SETTINGS-001 | Draft → proof → publish, connections/secret sources, rotation/scope tests; key-balancer не обязателен |
| ACCESS-001 | A-28/AD-09, ограниченное делегирование персоналу | AUTH-002, ADMIN-001 | Scope/expiry/delegation/last-owner, negative access; до реальных сотрудников |
| LOCAL-001 | Outbound agent, A-13/A-14/AD-05; S-39…S-43 | JOBS-001, API-001, CATALOG-001 | GPU outage не останавливает API; revoke, stale lease, approved workflows, no DB access |
| PLATFORM-001 | Telegram U-07/U-27/A-23, S-51 | AUTH-002, IMAGE-001 | Подписанные данные + реальный клиент, input/download/back/keyboard; не только JS hint |
| PLATFORM-002 | MAX U-08/U-27/A-23, S-52 | AUTH-002, IMAGE-001 | Собственный signed protocol + реальные клиенты; общий Account и UI |
| FEED-001 | U-21…U-23, D-06…D-08, A-19/A-20/AD-07; S-44…S-46 | MEDIA-001, ADMIN-001, IMAGE-001 | Publication/report/moderation/unpublish, private original закрыт; reactions отдельно включаемы |
| CHAT-001 | U-15/U-16/D-14, S-21 | AUTH-002, CREDIT-001, ENTITLEMENT-001, IMAGE-001, API-001 | Streaming/history + image tool, бюджет/ownership/confirmation, disconnect/injection negative tests |
| IMAGE-002 | U-11 и расширенные image modes | IMAGE-001, MEDIA-001, API-001 | Поддержанные references/masks, source сохранён; отдельная UX приёмка editor |
| VIDEO-001 | U-12 + result в U-20 | JOBS-001, MEDIA-001, API-001 | Один capability, duration/poll/reconcile/cancel cost, poster/full distinction |
| AUDIO-001 | U-13 + result/player/transcript | JOBS-001, MEDIA-001, API-001 | Сначала одна из ASR/TTS/music; mic denial, файл/cost/ownership; не обещать остальные |
| THREE-D-001 | U-14 + viewer/manifest | JOBS-001, MEDIA-001, API-001 | Safe resources, format/memory limits и fallback poster |
| SUPPORT-001 | U-34…U-36/D-11, A-21/A-22, S-65 | AUTH-002, ADMIN-001, MEDIA-001 | Own tickets, guest contact без account history, case-bound compensation/attachments |
| ACCOUNT-DATA-001 | U-37/D-12, S-47…S-49/S-66 | AUTH-002, MEDIA-001, CREDIT-001, JOBS-001 | Export/delete/fresh auth, grace/holds/active refs, restore-safe deletion; сроки отдельно принять |
| NOTIFY-001 | U-33/A-24, delivery в A-23; S-53…S-55 | AUTH-002, JOBS-001 | Inbox/outbox, идемпотентная доставка; real bot/email только при разрешении и consent |
| BILLING-001 | U-29…U-32/U-41/D-13, A-25/A-26/AD-10, S-60 | CREDIT-001, ENTITLEMENT-001, ADMIN-001, API-001, OPS-001 | Verified provider event/refund/idempotency; юр. решения, реальные вызовы по разрешению |
| OPS-001 | Staging/health/restore/release, A-01/A-30; S-57…S-59/S-62 | IMAGE-001, API-001 | Exact artifact, backup restore, scoped secrets/alerts/controlled release; не только down/up |
| LAUNCH-001 | U-01/U-38…U-40/U-42/U-43, S-61/S-63/S-64; выбранный публичный scope | F0-ACCEPT, принятые включённые функции, AUTH-002, SUPPORT-001, ACCOUNT-DATA-001, OPS-001 | Реальные claims, правовые документы, все launch gates; PLATFORM/FEED/BILLING обязательны только если объявлены |

S-01…S-08 технически валидируются уже в AUTH-001; SETTINGS-001 лишь даёт staff UI используемым policy, а не переписывает auth. Аналогично API-001 может иметь одно серверное проверенное connection из конфигурации до полной админки CATALOG-001. Реестр не создаёт циклическую зависимость «сначала все settings, потом первая функция».

U/A функциональны только после своей реализации, UI-прототип UX-001 не закрывает IMAGE-001. Public legal тексты — LAUNCH-001, не доказательство правомерности шаблона. Новые plans и увеличение квот вводятся только после выбранных чисел/стоимости, без переноса старых тарифов по умолчанию.

## 3. Карточки ближайших работ

### F0-ACCEPT

Scope: прочитать diff PR #1, точный SHA/CI и документацию; проверить boundaries, locks, actual commands, изоляцию, license-status. Защита main/required checks и reviewer проверяются отдельно, не считаются включёнными из-за AGENTS/CODEOWNERS. Исправления найденного дефекта — узким scope. Не добавлять новые AI/UI-функции и не деплоить. Результат — принятое исходное состояние и явный перечень незакрытых gates.

### UX-001

Предметные входы: PRODUCT U-09/U-10/U-18/U-19/U-20, общие D, UX и отрицательная оценка нынешнего shell. Результат: одна концепция с навигацией studio → running/error/result → private gallery. Пример A-03 нужен для проверки общих компонентов, не для реализации административных операций.

Scope: web components/styles/fake data, UI tests и предметная документация. Не менять backend/SQL/credits/providers/Docker/workflow/LICENSE. Разработка тестового viewport профиля разрешена внутри web; не ослаблять существующие проверки. Реальные ключи/платные вызовы запрещены.

Acceptance: phone/tablet/desktop/QHD2560×1440/UHD3840×2160; HiDPI1920×1080×2 и2560×1440×1.5; long Russian text, focus/keyboard/overflow/safe areas, price/result clarity. OS125/150/200% и реальные Mini Apps отдельно маркируются как проверенные или нет. Никакого общего transform:scale вместо адаптации. Evidence содержит viewport/DPR/browser/zoom и явные fake states. Владелец принимает визуал отдельно от CI.

### AUTH-001 → CREDIT-001 → ENTITLEMENT-001 → ADMIN-001

Последовательные ограниченные изменения, не одна мегазадача. AUTH даёт доверенный Account/session и минимальные permissions. CREDIT вводит ledger и concurrency. ENTITLEMENT описывает один basic plan revision и реальные deny decisions для zero/expired/quotas. ADMIN — только карточка и compensation/audit, case может завести сотрудник без ещё не готовой ticket-системы.

До приёмки требуются AC/AP сценарии, относящиеся к пакету: чужой account denied, forged/replayed session/CSRF, no self-admin, one grant per case, race reserve, no overspend, metadata/private scope. Пароль/token не видны в logs/artifacts. Тестовые значения помечены; регистрация не обещает бонус автоматически.

### MEDIA-001 → JOBS-001 → IMAGE-001

MEDIA реализует private upload/finalize/read; JOBS — durable state/attempt/lease/worker; IMAGE соединяет это с принятой оболочкой. Нельзя закрыть JOBS тестами enum или IMAGE скриншотом fake API.

На двух аккаунтах через настоящий изолированный backend проверить: duplicate submit, чужой input, cancel race, bad-job isolation, API/worker restart, S3 failure после result, unknown provider outcome, late/stale completion. DB/objects/баланс сохраняются. Один опубликованный fake screenshot не доказательство end-to-end.

### CHANGE-001 и API-001

До разрастания выполнить три обычные правки с фактическим измерением расхода/попыток/области. Только затем реальный provider c одним key/connection и установленным budget. Contract/errors проверяются fake; реальный вызов отдельно разрешён. Добавление adapter не создаёт новую auth/gallery/ledger систему. Не начинать key-balancer и все модальности одновременно.

## 4. Проверяемость и работа агентов

Любая экранная задача указывает U/D/A/AD-ID, state/entitlement из PRODUCT, permission/S-ID из ADMIN и один ID пакета. Для одного UI-label не читать все 66 групп настроек. Если задача затрагивает новый экран/поле, сначала добавить строку в существующий документ-владелец, не новый master plan.

Для каждого реализованного экрана: вход и доступ, данные/actions, success/empty/error/denied/refresh, ссылка на tests и ограничения реального клиента. Для S-группы — SV-01…SV-08; для прав — AC/AP отрицательные случаи. Это ещё не выполненные тесты DOC-003. Source of truth — actual code/contracts, спецификация меняется вместе с осознанным scope, не задним числом для оправдания дефекта.

Нерешённые provider price/retention не мешают UX/fake development. Они блокируют только включение реальной соответствующей функции. Merge не deploy; самостоятельная проверка не независимый review. Все фактические изменения и evidence агрегируются только в STATUS/Checks/PR.
