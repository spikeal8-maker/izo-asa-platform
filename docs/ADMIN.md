# Администрирование IZO ASA · спецификация 0.2

DOC-003, 8 сентября 2026. Целевой контракт, **не готовая админка**. У Foundation есть только оболочка /admin. Состояние — [STATUS](STATUS.md), этапы — [NEXT](NEXT.md), пользовательские страницы/доступ — [PRODUCT](PRODUCT.md), провайдерский runtime — [AI_RUNTIME](AI_RUNTIME.md).

## 1. Принцип и границы

Административная страница вызывает те же доменные команды Accounts/Credits/Generation/Media, что и другие разрешённые клиенты. Она не реализует второй баланс, прямую правку job status SQL или отдельную галерею. Сервер проверяет permission, scope, состояние сотрудника и свежесть аутентификации на каждом действии. Скрытый пункт меню не защита.

Матрица v0.2 и имена permissions — предлагаемый контракт для принятия. На старте может быть один назначенный оператор-владелец; это не требование нанять отдельную команду. Начального владельца назначает контролируемая операторская процедура, не public signup. Нельзя удалить/разжаловать последнего действующего владельца доступа без проверенного пути восстановления.

Право управлять продуктом не даёт права видеть все приватные файлы или секреты. Нет login-as-user, произвольного shell, SQL-console, загрузки executable plugin через админку и кнопки отключения обязательных security checks. Worker не пользователь и не GitHub runner. Покупка тарифа никогда не создаёт staff-role.

## 2. Permissions, роли и отказ

| Набор | Чтение по scope | Разрешённые мутации | Запрет по умолчанию |
|---|---|---|---|
| SUPPORT | users.read_limited, jobs.read_limited, support.read | support.respond, support.compensation_request | Начислять, менять роли/keys, открывать чужую переписку без case-grant |
| MODERATION | moderation.read, publication/report metadata | moderation.decide, publication.hide, report.respond | Всю private gallery автора и его sessions/деньги |
| FINANCE | credits.read, plans.read, payments.read | credits.grant/adjust, plans.write, pricing.write, payments.refund в лимите | Raw card/key data; менять staff permissions |
| PROVIDER_OPS | catalog.read, connections.read, workers.read, jobs.read_technical | catalog.write, connections.write, workers.manage, jobs.reconcile; secrets.bind только с отдельным grant | Изменять баланс/цену или произвольный endpoint вне egress-policy |
| ACCESS_OWNER | access.read, audit.read по разрешённому scope | access.manage, users.restrict, sessions.revoke, policy.publish | Обход audit/ledger, чтение сохранённого пароля/ключа |

Это наборы granular permissions, не сравнение «role level >= 3». OWNER продукта может иметь объединение наборов, но каждая sensitive command всё равно требует явного разрешения/fresh auth/reason. metadata read не подразумевает чтение private payload. Права на pricing, secrets и экспорт назначаются отдельно, даже если поле находится рядом на одном экране.

Дополнительные разрешения: media.read_metadata; media.review_private с привязкой к конкретному support/moderation case, объекту и сроку; media.quarantine; policy.read/write/publish по группе; audit.export; support.data_request_execute; delivery.manage; system.read. Не выдавать глобальный media.review_private лишь для страницы списка.

Нет permission → 403 без данных/побочного эффекта; чужой private ID в неподходящем scope → безопасное not_found. В audit записывается безопасный отказ. Отзыв staff grant/блокировка сотрудника запрещает следующий запрос независимо от открытой вкладки. Для просмотра прав применяется permission read, изменение не выдаётся автоматически.

## 3. Реестр административных страниц

A — экран/route с вкладками, AD — диалог. Маршруты целевые; DOC-003 их не добавляет. Все A доступны только действующему staff с указанным permission и scope; каждый tab/API проверяется отдельно. В таблицах обязательны фильтр/пагинация, loading/empty/error/stale data, not found/denied. В forms — validation, busy, conflict/expectedRevision, success receipt. Общие требования UX включают телефон, tablet, QHD/4K и HiDPI, а не только desktop.

| ID · маршрут · вход | Permission / данные | Действия → результат | Приёмка/ограничение | Пакет |
|---|---|---|---|---|
| A-01 `/admin` · staff menu | system.read; обзор availability/queue/spend в scope | Drill-down к A-15/A-30 | Интервал/свежесть; отсутствие jobs не равно unhealthy | OPS-001 |
| A-02 `/admin/users` · nav | users.read_limited; code/name/status | Search/filter → A-03 | Не загрузить весь PII-каталог без цели; paging | ADMIN-001 |
| A-03 `/admin/users/{accountId}` · список/заявка | users.read_limited; tabs обзор/identity/sessions/jobs/media/credits/tickets/audit по своим правам | AD-01/AD-02, профиль разрешённых grants | Нет скрытой второй CRM; sensitive tab не читается заранее | ADMIN-001, затем профильный пакет |
| A-04 `/admin/credits` · nav/account | credits.read | Поиск проводки/резерва, AD-01 corrective action | Журнал неизменяем; missing usage не = 0 | CREDIT-001, ADMIN-001 |
| A-05 `/admin/compensations/{caseId}` · case/account | credits.grant + limit, support scope | Основание/история → AD-01 | Один grant на business case; не только UUID клика | ADMIN-001 |
| A-06 `/admin/plans` · nav | plans.read; draft/published versions | plans.write → A-07 | Новые планы выключены; тариф не staff-role | ENTITLEMENT-001 |
| A-07 `/admin/plans/{planId}` · список | plans.write/pricing.write отдельно; поля S-09…S-23 | Редактировать draft → AD-08 publish | Diff прав/квот, effectiveAt, влияние на действующие планы | ENTITLEMENT-001, BILLING-001 |
| A-08 `/admin/models` · nav | catalog.read | Import candidates/filter → A-09 | Discover не публикует платные модели | CATALOG-001 |
| A-09 `/admin/models/{capabilityId}` · список | catalog.write; schema/inputs/outputs/provider/pricing отдельно | AD-03 publish/disable, разрешённый probe | Immutable snapshot у jobs; поддержанные modes подтверждены | CATALOG-001 |
| A-10 `/admin/providers` · nav | connections.read | Список provider adapters/connections → A-11 | Adapter не создаётся вводом JS/Python в UI | CATALOG-001 |
| A-11 `/admin/providers/{providerId}/connections/{connectionId}` · provider | connections.write; account/project, endpoint, limits, credential metadata | Настроить draft, AD-04, enable/drain/probe | Другой account/key source не перехватывает старый job | CATALOG-001 |
| A-12 `/admin/credentials` · connection | secrets.bind отдельный scope | Metadata, input/rotate/revoke AD-04 | Write-only; не raw env/browser-localStorage/log | CATALOG-001 |
| A-13 `/admin/workers` · nav | workers.read | Pools/version/last heartbeat → A-14 | Off-line GPU не ломает API status | LOCAL-001 |
| A-14 `/admin/workers/{workerId}` · список | workers.manage; capabilities/lease/занятость | AD-05 register/revoke/drain | Token scope ограничен; никаких arbitrary remote commands | LOCAL-001 |
| A-15 `/admin/jobs` · nav/account | jobs.read_technical | Filter state/age/provider → A-16 | Redacted prompt/error; scope пользователя/case где нужен payload | JOBS-001 |
| A-16 `/admin/jobs/{jobId}` · список/alert | jobs.reconcile; attempts/fencing/provider refs/cost | AD-06 reconcile/cancel/redownload | Не новый paid submit под названием «исправить» | JOBS-001, API-001 |
| A-17 `/admin/media` · nav | media.read_metadata | Size/type/status/orphan filters → A-18 | Не public file manager; originals не prefetch | MEDIA-001 |
| A-18 `/admin/media/{assetId}` · job/case | media.read_metadata; private preview требует media.review_private | AD-07 quarantine/review, lineage | Только case-bound access; destructive delete отдельно от preview | MEDIA-001, ACCOUNT-DATA-001 |
| A-19 `/admin/feed` · nav | moderation.read | Pending/published/hidden, решение AD-07 | Решение версии публикации, не старого cached preview | FEED-001 |
| A-20 `/admin/reports/{reportId}` · moderation list | moderation.decide | Предмет/reason/appeal → решение | Не раскрывать заявителя другим пользователям | FEED-001 |
| A-21 `/admin/support` · nav | support.read | Очередь/status/assignee → A-22 | Limit scope и SLA без обещанных чисел | SUPPORT-001 |
| A-22 `/admin/support/{ticketId}` · очередь | support.respond; связанные account/jobs | Ответ, escalation, request case-grant, A-05 | Вложения не произвольные server paths; нет повторного начисления | SUPPORT-001 |
| A-23 `/admin/integrations` · nav | delivery.manage; tabs Telegram/MAX/email | Draft config, explicit apply/probe | Изменение bot webhook — отдельное подтверждённое действие | PLATFORM-001, PLATFORM-002, NOTIFY-001 |
| A-24 `/admin/notifications` · integrations | delivery.manage; outbox attempts | Pause/retry delivery существующего события | Retry не повторяет grant/generation; consent сохраняется | NOTIFY-001 |
| A-25 `/admin/payments` · nav | payments.read | Orders/events/reconciliation filters → A-26 | Не live до разрешённой интеграции | BILLING-001 |
| A-26 `/admin/payments/{paymentId}` · список | payments.refund/pricing отдельно | Сверить/AD-10 refund | Проверенный provider event; двукратный refund исключён | BILLING-001 |
| A-27 `/admin/settings` · nav | policy.read/write по группе | Brand/features/security/storage/support/privacy → AD-08 | Runtime policy ≠ Docker/env-console; секреты в A-12 | SETTINGS-001 |
| A-28 `/admin/access` · nav | access.manage | Staff sets/scopes/limits, AD-09 | Запрет self-escalation/последнего owner; fresh auth/audit | ACCESS-001 |
| A-29 `/admin/audit` · nav/receipt | audit.read/export по scope | Фильтр actor/command/target/time/request; разрешённый export | Нельзя менять/стирать event; redaction PII/secrets | ADMIN-001, OPS-001 |
| A-30 `/admin/system` · nav/alert | system.read | Versions/schema/health/pools/backup receipt, ссылки runbook | Без shell, release/restart buttons в первом объёме | OPS-001 |

Минимальная A-03/A-04/A-05/A-29 входит в alpha, остальные появляются со своим пакетом. В одном early operator UI можно объединить навигацию, но permissions и команды не сливаются. Полный набор страниц не требуется писать до первой image-generation.

## 4. Карточка пользователя и административные диалоги

A-03 имеет tabs: overview; identities; sessions; jobs; media metadata; credits; support; audit. Названия полей: immutable account ID/public code, display name, state, verified methods, effective plan/revision/expiry, available/reserved credits, created/last active. Email/session details маскируются по scope. IP/платформа не доказательство физической личности; MAC не собирается.

| ID | Родитель | Поля/действие | Обязательное подтверждение/выход |
|---|---|---|---|
| AD-01 Grant/adjust | A-03/A-04/A-05 | recipient, case ID, integer credits, reason, evidence reference, operation key | Summary, actor limit, receipt; изменить прошлую проводку нельзя |
| AD-02 Ограничение/сессии | A-03 | generation_suspend/security_lock/unlock/revoke, reason, scope | Предупредить о pending jobs; state transition из PRODUCT §12; не стереть баланс |
| AD-03 Модель | A-09 | schema/version/diff, paid test budget отдельно | Test evidence, publish/disable effectiveAt; no auto discovery → live |
| AD-04 Секрет | A-11/A-12 | source/binding, target account/project/environment, new secret через write-only канал | Fresh auth; mask receipt; rotation/revocation и незавершённые attempts |
| AD-05 Worker | A-14 | allowed pools/capabilities, limit, drain/revoke | Scoped enrollment, token показан только при создании где требуется; не real key в audit |
| AD-06 Задание | A-16 | reconcile/cancel/finalize-existing; reason | Факт provider acceptance/outcome; новый submit требует отдельного разрешения/бюджета |
| AD-07 Модерация | A-18/A-19/A-20 | target version, decision, reason, appeal reference | Автор/время/audit, закрыть public derivatives, не чужой original |
| AD-08 Настройка | A-07/A-27 и config tabs | draft, expected revision, diff, effectiveAt, reason | Validation → impact preview → publish; conflict не перетирает чужое изменение |
| AD-09 Полномочия | A-28 | staff subject, known permissions, scope/expiry/limits | Fresh auth и отдельное право delegation; нельзя выдать больше доступного для делегирования |
| AD-10 Refund | A-26 | payment/refundable amount, currency, reason, operation key | Verified status, предел возврата, идемпотентный provider request, ledger link |

## 5. Компенсация после перезапуска

Новый аккаунт → case с основанием → уполномоченный сотрудник → AD-01 → одна транзакция command claim + ledger/projection + audit/outbox → receipt и история пользователя. Сумма положительная, целочисленная, не превосходит actor limit; target проверяется до подтверждения.

Повтор operation key с тем же payload возвращает прежний результат; другой payload — conflict. Уникальный business case защищает даже повтор с новым operation key. Исправление — новая компенсирующая проводка со ссылкой на исходную, не редактирование/удаление старой. Уведомление о начислении может повторяться идемпотентно, само начисление — нет.

Первый ADMIN-001 допускает case, заведённый сотрудником вручную, до готового SUPPORT-001. Это не требует импорта старой базы или работающей пользовательской ticket-системы. Self-service D-11 подключается позже к тому же case ID.

## 6. Модели, подключения и ключи

Оригинальные §9–10 [AI_RUNTIME](AI_RUNTIME.md) — владелец protocol/credential rules. Здесь описана их административная поверхность: capability отдельно от adapter, connection/account/project, credential binding и secret source.

Новая модель/connection выключены. Сначала валидируется draft/capability и fake-contract; реальный probe только с отдельным разрешением/бюджетом, затем publish. Catalog change не меняет snapshot текущего job. Disable запрещает новые submissions, drain сохраняет допустимые poll/finalize. Revoked/утёкший key не используют ради завершения работы; такие attempts переходят в ограниченную сверку.

401/403 не запускает перебор ключей; 429 учитывает provider/account limit и Retry-After. Разные keys одного аккаунта не считаются отдельными квотами. Другой provider/account/fallback требует явной политики стоимости и допустимости передачи входных данных. UI и ledger остаются общими, результат/цена разных моделей не обязаны совпадать.

## 7. Разбор зависших задач

A-16 показывает job/attempt IDs, status/version, provider reference, last heartbeat/lease/fencing, время фаз, reservation/settlement и redacted error. Отдельно видно: отправки не было, принята provider, outcome неизвестен, result доступен, upload/finalize не завершён.

Разрешённые действия — сверить статус, повторить сохранение существующего результата, запросить отмену, оформить outcome по policy с audit. Ручная установка succeeded без проверенного asset/settlement запрещена. Новая платная попытка не прячется за кнопкой «Восстановить». Поздний callback со старым fencing token не меняет terminal state.

## 8. Аудит и приёмка staff-действий

Audit содержит actor, permission/scope snapshot, action, target/version, reason, redacted before/after, operation/request ID, timestamp. Отказ sensitive command тоже фиксируется безопасно. Secret value заменяется фактом/версией изменения. Private case preview регистрируется как чтение по цели, не молчаливый доступ владельца ко всему.

Обязательные будущие tests: AP-01 nonstaff denied; AP-02 staff scope crossing denied; AP-03 одно начисление при race; AP-04 key отсутствует в API/log/exception; AP-05 role revoke немедленно проверяется; AP-06 private preview требует case-grant; AP-07 смена модели не меняет текущий job; AP-08 hidden publication недоступна; AP-09 audit и конфигурация фиксируются атомарно; AP-10 новый grant не обходит actor limit/last-owner rule.

## 9. Общий контракт настроек

S-ID идентифицирует **группу типизированных полей**, не свободный JSON без схемы. Имена ниже — целевые config keys; существующих env/runtime fields с такими именами пока может не быть. Настройки вводятся рядом с функцией, а не универсальным редактором всей системы заранее.

Каждая группа имеет key/schema version, label/help, scope (environment/global/plan/capability/connection/worker), value/type/unit, допустимые ограничения, default/inheritance, read/write permission, apply mode и audit. Нулевой лимит = запрет; null = только явно описанное наследование. Неизвестные поля/permissions/enum отвергаются. Неограниченность нельзя прятать в -1.

Обозначения defaults: **REQ** — явное значение обязательно до включения этой функции в production; пока его нет, публикация конфигурации отклоняется с указанием поля. Это не запрещает бесплатный dev/fake prototype. **DRAFT** — стартовое предлагаемое техническое значение, не утверждённая бизнес-политика. Числа в таблице — для будущей реализации/обсуждения, не изменение действующего сервиса.

Применение: **V** — новая revision для новых операций/quotes; текущие jobs сохраняют snapshot. **I** — ограничение/visibility применяется следующим запросом; уже принятый внешний вызов не объявляется отменённым автоматически. **SESSION** — ужесточение переоценивает/отзывает затронутые сессии. **DELIVERY** — только новые доставки/маршрутизация, никогда не повтор доменного действия. **OPS** — только операторский deployment/runbook, не editable setting в обычной админке.

Любое publish проходит AD-08: schema validation, проверка permission и expected revision, cross-field проверки, impact preview, reason/confirmation, транзакционная новая version + audit/outbox. При conflict пользователь получает diff, не молчаливый overwrite. Откат создаёт новую revision предыдущих допустимых значений и **не откатывает БД, файлы или финансовые события**. Ужесточение security/доступа не откладывается ради старого UI-cache.

## 10. Каталог полей настроек

Все группы ниже наследуют проверки §9 и SV из §11. В записи «REQ» разрешённый диапазон всё равно определяется здесь или capabilities; агент обязан добавить конкретные технические hard bounds/единицы в schema перед реализацией, не считать отсутствие значения unlimited. Публиковать платные/опасные функции при неполной конфигурации нельзя.

### Доступ и планы

| ID · ключ / экран | Тип, допустимые значения/связи | Начальное значение | Кто / применение |
|---|---|---|---|
| S-01 `registration.mode` / A-27 | enum disabled/invite/public; invite требует одноразового invitation | DRAFT invite для alpha, public выключен | policy.write security / I |
| S-02 `auth.methods` / A-27 | Множество web_password/telegram/max; platform требует проверенной binding; нельзя убрать последний staff recovery | DRAFT web_password; platform выключены | policy.write security / SESSION |
| S-03 `session.idle_seconds` / A-27 | int 60…86400, <= absolute_seconds | DRAFT 1800 | policy.write security / SESSION |
| S-04 `session.absolute_seconds` / A-27 | int 900…2592000, >= idle_seconds | DRAFT 604800 | policy.write security / SESSION |
| S-05 `challenge.ttl_seconds` / A-27 | int 60…1800 для email/reset; platform freshness отдельно по SDK policy | DRAFT 600 | policy.write security / V |
| S-06 `challenge.max_attempts` / A-27 | int 1…10; счётчик на challenge, не сбрасывается repeat HTTP | DRAFT 5 | policy.write security / I |
| S-07 `login.throttle` / A-27 | object attempts int 1…100, window_seconds 60…3600; нормализованный subject + network policy, не полная блокировка сервиса | DRAFT 5/300; tune на staging | policy.write security / I |
| S-08 `staff.grants` / A-28 | Known permissions + scope + expires_at + delegation ceiling; deny неизвестным, last-owner rule | Пусто у signup; initial owner отдельной процедурой | access.manage / I |
| S-09 `plans.default_id` / A-07 | Ссылка на опубликованный basic revision; не случайная строка | REQ при включении generation | plans.write / V |
| S-10 `plan.capability_ids` / A-07 | Set существующих versioned capabilities; пусто = ничего | Пусто в новом draft | plans.write / V |
| S-11 `plan.executor_types` / A-07 | Set api/local, пересечение с capability; не служебные credentials | Пусто в новом draft | plans.write / V |
| S-12 `plan.active_jobs` / A-07 | int >=0, finite <= server safety bound; queued/claimed/running/uploading/reconciling считаются, terminal нет | REQ, 0 запрещает новые jobs | plans.write / V; reduction не убивает текущие |
| S-13 `plan.submission_window` / A-07 | Object limit int >=0, window_seconds int >0; новые принятые jobs, не poll/dedup | REQ | plans.write / V |
| S-14 `plan.storage_bytes` / A-07 | int >=0; committed + pending reserved bytes, safe cleanup освобождает учёт | REQ; 0 запрещает новое хранение | plans.write / V; чтение сохраняется |
| S-15 `plan.upload_limits` / A-07 | max_file_bytes int >=0, max_inputs int 0…32; <= ingress/decoder/capability limits | REQ для upload | plans.write / V |
| S-16 `media.input_mime_allowlist` / A-27 | Set зарегистрированных decoder types, реальное sniffing; не разрешать произвольный HTML/SVG/script как изображение | REQ; пусто запрещает upload | policy.write media / V |
| S-17 `plan.image_sizes` / A-07 | Set пар positive width/height; <= adapter/safety pixels; quality/count отдельно в schema | REQ; 4K-монитор не добавляет 4K-generation | plans.write / V |
| S-18 `plan.video_max_seconds` / A-07 | int >=0, <= capability duration maximum | 0, пока video выключено | plans.write / V |
| S-19 `plan.audio_max_seconds` / A-07 | int >=0, <= input/output capability limits | 0, пока audio выключено | plans.write / V |
| S-20 `plan.mesh_limits` / A-07 | Object bytes/triangles/texture_pixels: finite ints >=0, <= viewer/adapter safety | REQ до 3D, иначе 3D off | plans.write / V |
| S-21 `plan.chat_limits` / A-07 | context_tokens/active_requests/tool_calls/max_action_credits finite ints >=0; context <= model maximum, денежный cap отдельный | REQ до chat, otherwise off | plans.write / V |
| S-22 `plan.publishing` / A-07 | can_publish/can_react bool + limits int >=0; действует и moderation policy | false в новом draft | plans.write / V |
| S-23 `plan.validity` / A-07 | effective_from/expires_at UTC; конец > начало; expiry → базовая действующая revision, не удаление баланса/файлов | REQ для временного назначения | plans.write / V |

### Модели, подключения, стоимость и локальные исполнители

| ID · ключ / экран | Тип, допустимые значения/связи | Начальное значение | Кто / применение |
|---|---|---|---|
| S-24 `capability.presentation` / A-09 | name 1…120 chars, help <=2000, supported modalities/inputs из schema; без false claims | Draft, не опубликован | catalog.write / V |
| S-25 `capability.publication` / A-09 | draft/published/disabled + evidence refs; опубликованное требует adapter/connection/pricing/entitlements | draft | catalog.write / I для disable, V для новой версии |
| S-26 `capability.adapter_model` / A-09 | adapter ID из code registry + model ID по provider schema; изменяется новой version | REQ; arbitrary code запрещён | catalog.write / V |
| S-27 `connection.scope` / A-11 | provider/account/project/environment IDs; unique binding, принадлежность валидируется | REQ | connections.write / V |
| S-28 `connection.endpoint` / A-11 | HTTPS URL в отдельном operator allowlist; no embedded auth/private metadata endpoints/unsafe redirect | REQ; новый адрес не добавляет себя в allowlist | connections.write / V; allowlist OPS |
| S-29 `credential.binding` / A-12 | type secret_file/secret_manager + opaque ref/version; dev-env только в dev; отдельный write-only ввод при поддержке store | Unbound = нельзя включить connection | secrets.bind / I revoke, V rotate |
| S-30 `connection.state` / A-11 | disabled/active/draining; active только после безопасной проверки | disabled | connections.write / I |
| S-31 `connection.max_concurrency` / A-11 | int >=0 <= provider/account/resource safety cap; 0 stop новых calls | REQ; off до конфигурации | connections.write / I новые claims |
| S-32 `provider_account.rate_limit` / A-11 | requests int >=0 / window_seconds >0, scope account/project, общий для связанных keys | REQ/проверенный provider limit | connections.write / I |
| S-33 `provider_account.spend_cap` / A-11 | Decimal/minor units >=0 + currency + period UTC; учитывать pending cost liability; unknown cost не ноль | 0 для live до согласованного бюджета | pricing.write / I новые расходы |
| S-34 `adapter.timeouts` / A-11 | connect/read/overall seconds >0; bounded по API version; общий deadline не равен timeout короткого polling | REQ для конкретного adapter | connections.write / V |
| S-35 `adapter.safe_retries` / A-11 | int 0…5 + backoff; только доказанно не принятые/idempotent calls, не unknown submit | DRAFT 2; при unknown сначала reconcile | connections.write / V |
| S-36 `routing.failover` / A-11 | enabled bool + explicit target connection allowlist + budget/disclosure policy; no blind key cycling | false | connections.write + pricing.write / V |
| S-37 `pricing.rule` / A-09 | fixed/reserve_settle + finite integer credits/max + schema version; unknown usage нельзя заменить 0 | REQ до paid publication | pricing.write / V |
| S-38 `pricing.quote_validity` / A-09 | ttl_seconds 30…900; request hash/currency/fx source version when applicable; repeat после expiry требует новой quote | DRAFT 120; курс REQ если нужен | pricing.write / V |
| S-39 `worker.capability_allowlist` / A-14 | Set approved capabilities/workflow versions; не объявление самого worker | Пусто | workers.manage / I новые claims |
| S-40 `worker.max_concurrency` / A-14 | int >=0 <= зарегистрированный resource cap; ограничение по GPU/pool | 0 до приёмки worker | workers.manage / I, active drain |
| S-41 `worker.credential_binding` / A-14 | Scoped token ID/version/expiry; raw token не читается после enrollment, revocation instant | REQ | workers.manage / I |
| S-42 `worker.lease_policy` / A-27 | heartbeat_seconds >0; lease_seconds >=3×heartbeat, ограничены reviewed schema; fencing обязателен | DRAFT heartbeat20/lease90 | policy.write runtime / V |
| S-43 `reconciliation.policy` / A-27 | deadline_seconds >lease + escalation target + outcome rules; не retry-paid-after-timeout flag | REQ до live provider | policy.write runtime / V |

### Публикация, хранение, доставка и система

| ID · ключ / экран | Тип, допустимые значения/связи | Начальное значение | Кто / применение |
|---|---|---|---|
| S-44 `feed.mode` / A-27 | closed/premoderated; открытие требует report/moderation workflow | closed | policy.write moderation / I |
| S-45 `publication.public_fields` / A-27 | Allowlist title/caption/public_author/approved_derivative; prompt только explicit opt-in, references не implicitly public | Минимальные публичные metadata | policy.write moderation / V |
| S-46 `feed.interactions` / A-27 | reactions bool, reports limit/window finite; жалобы должны работать при открытом feed | Reactions false; reports REQ для feed | policy.write moderation / I |
| S-47 `deletion.grace_seconds` / A-27 | int >=0 + effective policy notice; нельзя purge активные refs/holds | REQ до user deletion | policy.write data / V |
| S-48 `retention.originals` / A-27 | days positive finite или explicit keep_until_owner_delete; исключения/notice; storage cap отдельно | Нет автозачистки до принятой policy | policy.write data / V; cleanup отдельный процесс |
| S-49 `retention.temporary` / A-27 | Upload/orphan/derived срок >0; cutoff только после ref/lease проверки; public active derivative не orphan | REQ до cleanup | policy.write data / V |
| S-50 `media.preview_profiles` / A-27 | Versioned size/format/quality набор из trusted encoder schemas, <= source/safety budget | REQ; UI uses size/DPR, не full4K на каждой карточке | policy.write media / V новые derivatives |
| S-51 `platform.telegram` / A-23 | bot ID, HTTPS origin, secret binding ref, auth freshness policy; webhook target из allowlist | disabled до PLATFORM-001 | delivery.manage + secrets.bind по отдельности / explicit apply |
| S-52 `platform.max` / A-23 | Собственные bot/app ID, origin/bridge validation и credentials, не копия Telegram-algorithm | disabled до PLATFORM-002 | delivery.manage + secrets.bind / explicit apply |
| S-53 `notifications.channels` / A-23 | inbox/email/telegram/max set; user opt-in/verified destination; staff не включает согласие за пользователя | DRAFT inbox; external off | delivery.manage / DELIVERY |
| S-54 `delivery.retry_policy` / A-24 | max_attempts int 0…10, backoff bounded; idempotent event ID | DRAFT 3 | delivery.manage / DELIVERY |
| S-55 `mail.connection` / A-23 | Driver, sender verified identity, server allowlist, TLS policy, secret ref; no downgrade/TLS-off | disabled, REQ для public email-login | delivery.manage / explicit apply |
| S-56 `compensation.policy` / A-27 | staff_only/self_service_request; max_grant_per_actor integer >=0, duplicate-case policy; user не управляет amount | staff_only; limit REQ перед первым grant | policy.write credits / I |
| S-57 `audit.retention` / A-27 | Positive days + approved exceptions/holds + access scope; не editable audit records | REQ для production | policy.write audit / V; sensitive review |
| S-58 `maintenance.mode` / A-27 | off/pause_new_jobs/read_only; session recovery/help доступны, security lock отдельно | off | policy.publish operations / I |
| S-59 `features.release_flags` / A-27 | Known implemented capability/page IDs; incomplete function нельзя включить generic bool | Все неготовые функции off | policy.publish release / I |
| S-60 `billing.connection` / A-23 | enabled bool, provider/merchant/test-live scope, credentials ref, callbacks; live после BILLING-001 | disabled | payments.configure + secrets.bind / V; apply separately |
| S-61 `legal.documents` / A-27 | slug/version/hash/effectiveAt/content URL в approved origin; точный список U-38…U-43 | REQ перед launch; не fabricated text | policy.publish content / V |
| S-62 `operations.alerts` / A-27 | Metric ID/finite threshold/window/recipient & escalation; отсутствие queued jobs не alert | REQ для OPS-001 | policy.write operations / I |
| S-63 `brand.presentation` / A-27 | Public name <=120, description <=500, approved links/logo asset ID; asset licence проверена | IZO ASA; остальные только подтверждённые | policy.write content / V |
| S-64 `ui.default_theme` / A-27 | light/dark/system; личный выбор приоритетнее; design tokens не arbitrary CSS | Предлагаемый light, согласовать UX-001 | policy.write content / V новые preferences |
| S-65 `support.contact` / A-27 | Проверенный public email/URL/contact route; не secret/private employee address | REQ до launch | policy.write support / I |
| S-66 `data.export_policy` / A-27 | signed_ttl_seconds 60…3600, request rate finite, reauth required; owner/case scope | DRAFT ttl900; rate REQ | policy.write data / V |

Управление `staff.grants` S-08 — типизированная операция с собственным API, не массовая замена произвольного JSON. Аналогично S-29/S-41 не чтение secret store: публикуется metadata reference; ввод/revoke — AD-04/AD-05. API-user не может прислать эти keys в generate-request.

### Что не редактируется как настройка продукта

DB/S3 root credentials, Docker socket, container image tags/digests, network/egress allowlists, server filesystem roots, hard resource limits, backup destinations/keys, TLS certificates, миграции, branch protection и CI permissions — **OPS**, операторский путь из [OPERATIONS](OPERATIONS.md). A-30 показывает безопасный статус, не право изменить инфраструктуру. Реальный секрет поставщика может вводиться через защищённый secret workflow, но не через общий текстовый редактор env.

## 11. Проверки настроек и критерий полноты

Для каждой реализованной S-группы нужен SV-01 allowed/forbidden actor/scope; SV-02 valid/boundary/invalid type и cross-field cases; SV-03 default/null/0 и запрет publish с REQ; SV-04 expectedRevision conflict/race; SV-05 audit/redaction; SV-06 применимость V/I/SESSION/DELIVERY и snapshot действующего job; SV-07 rollback новой revision без отмены ledger; SV-08 secret не попадает в UI/log/test artifact где применимо.

Нельзя считать общую таблицу формальным разрешением создать 66 экранов сразу. SETTINGS-001 вводит только типизированный lifecycle и настройки ближайшей функции; поле появляется вместе с его consumer/test. Иначе админка снова станет огромным неиспользуемым конфигуратором.

Новая A/AD/S добавляется сначала в этот реестр с permission, apply semantics и пакетом NEXT. Существующая страница без своей карточки или новая настройка с неописанным default не считается завершённой. Документационный review проверяет ссылки/ID/полноту, runtime tests вводятся только вместе с кодом. Независимый security review не подменяется самопроверкой автора.

Источники security-принципов, проверены 2026-09-08: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html и https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html . Конкретные роли, поля и технические DRAFT defaults — предложение IZO ASA, не нормативные значения OWASP.
