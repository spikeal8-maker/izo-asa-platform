# Выполнение AI-запросов в IZO ASA · спецификация 0.1

Это целевой runtime-контракт. На канонической линии уже реализованы общие Credits/Entitlements/Media/Jobs, deterministic test executor и серверный fal.ai adapter/lifecycle для `fal.flux2.klein.4b`. Live fal request/provider billing остаются отдельной непроведённой приёмкой; local GPU-agent, универсальный provider catalog/credential registry и остальные modality runtimes ещё не реализованы. Процесс coding-агента описан отдельно в [DEVELOPMENT](DEVELOPMENT.md).

## 1. Разделение понятий

Modality — тип результата: image/video/audio/3d/chat. Capability — действие, например image.generate, image.edit, speech.transcribe. Provider — внешний сервис или локальный движок. Model — конкретная модель/версия. Executor — серверный API-worker или локальный worker. Pricing policy — отдельное правило, не capability модели.

Один registry не обязан выражать всю UI-логику через произвольный JSON. Поддерживаются явные типизированные input/parameter schemas и известные UI widgets. Неизвестное поле не становится автоматически исполняемой командой.

## 2. Регистрация и выпуск capability

Декларация версии содержит: идентификатор, действие/modality, provider/model, executor, inputs/outputs, count/size/duration limits, допустимые параметры, supported cancellation, streaming/polling, timeouts, concurrency/resource class, reconciliation method, pricing version и permission/visibility.

Не всякая модель поддерживает фото, mask, звук или tools. Несовместимый режим блокируется до резерва и вызова провайдера. Автообнаруженные модели выключены до теста и публикации оператором. Снимок capability/pricing сохраняется с заданием, изменение каталога не меняет уже принятые расходы и параметры.

## 3. Путь от кнопки до результата

1. Клиент отправляет намерение: capability/model choice, prompt, owner-scoped input asset IDs, параметры и idempotency key. Он не выбирает owner, secret, внутренний endpoint или цену.
2. Сервер проверяет session, доступ, schema, состояние аккаунта, принадлежность исходников и квоты.
3. Сервер выдаёт действующую оценку/верхний предел резерва и срок её применимости. Подтверждение связано с этими параметрами; изменение запроса требует новой оценки.
4. В транзакции проверяются request hash/idempotency, доступный остаток и создаются reservation + queued job + dispatch event. Повтор идентичного запроса возвращает тот же job; другой запрос с тем же ключом — conflict.
5. Подходящий executor атомарно получает attempt с lease/fencing token. API и local не занимают одну последовательную очередь; есть per-provider/GPU ограничения.
6. До внешней отправки фиксируется намерение dispatch и идентификатор попытки. Provider idempotency используется только если реально поддержан; его отсутствие документируется.
7. Adapter передаёт разрешённые входы, обрабатывает bounded timeout, status/stream/poll и сохраняет provider reference как можно раньше. Секреты не попадают в prompt, result и public error.
8. Результат валидируется, скачивается/загружается в карантинное или временное storage. Не доверять MIME/URL только по сообщению provider.
9. Финализация идемпотентно связывает готовые assets, terminal job и settlement. Повторный callback или поздний ответ старого attempt не создаёт вторую работу/проводку.
10. UI читает собственный job/asset, получает финальное состояние и галерею. Outbox доставляет уведомление независимо от результата генерации.
11. Reconciliation/cleanup завершают недоведённую финализацию и освобождают orphan objects по policy. Они не запускают новую платную генерацию ради существующего файла.

## 4. Состояния и отмена

Общий Jobs runtime уже использует durable состояния queued/claimed/running/uploading/succeeded/failed/cancelled/reconciling и дополнительные provider-reconciliation reason codes. Актуальный исполняемый граф принадлежит `apps/api/izo/jobs/` и его тестам; этот документ фиксирует общую семантику. Cancel request хранится как отдельное намерение и не считается гарантированным provider cancellation.

`queued` — принята и зарезервирована. `claimed` — выдан attempt. `running` — выполняется. `uploading` — результат готовится к сохранению. `reconciling` — известен сбой, но внешний outcome/финализация ещё не определены. Успех требует сохранённого доступного результата, не HTTP 200 provider.

Отмена до отправки освобождает резерв. После принятия provider применяется его реальная политика: запрос отмены не гарантирует остановку и возврат расходов. При гонке completion/cancel одно транзакционное решение определяет результат; UI не обещает возврат до подтверждения. Пользователь не оплачивает retry сети второй раз автоматически.

## 5. Матрица сбоев и ожидаемого поведения

| Событие | Ожидаемая реакция | Запрет |
|---|---|---|
| Двойной submit/повтор после timeout API | Один логический job и резерв | Два списания |
| Crash до фактической отправки | Восстановить claim по доказанному состоянию | Оставить вечный running |
| Crash после отправки до сохранения provider ID | reconciling; idempotency/status lookup, если доступны | Слепой новый платный запрос |
| 429/временная сеть до принятия | Bounded retry с backoff/jitter и квотой | Бесконечные повторы |
| Исчерпаны средства/неверный ключ provider | Остановить новые попытки, alert оператору, безопасная ошибка | Показать ключ или списать у пользователя за пустой результат |
| Provider выполнил, S3 временно недоступно | Повторить сохранение имеющегося результата | Повторить генерацию |
| Webhook дублируется/приходит не по порядку | Idempotent event/version handling | Регресс terminal state и повторная проводка |
| Local worker пропал | Lease expired → безопасная сверка; не использовать поздний fencing token | Автопереключение на paid API без согласия |
| Невалидный media/result | Quarantine, понятная ошибка, policy settlement | Выдавать HTML/скрипт как картинку |
| Ошибка outbox доставки | Отдельный retry уведомления | Перевести успешно созданную работу в failed |
| Оценка/фактическая цена разошлись | Применить заранее согласованный максимум/правило | Незаметный отрицательный баланс |

Reconciliation имеет собственный deadline и эскалацию оператору. Когда API не позволяет выяснить факт выполнения, состояние честно помечается нерешённым до решения по policy; exactly-once для такого provider не заявляется.

## 6. Локальный GPU-исполнитель

Local agent — отдельный сервис, не копия публичного backend. Bootstrap/регистрация выполняются оператором, agent получает отзывной scoped token и объявляет допустимые capabilities/версию. Сервер проверяет registry; произвольное объявление «умею всё» не даёт задач.

Связь: исходящий HTTPS polling/long-poll, heartbeat и result upload; прямой доступ из интернета к ComfyUI и домашней БД не нужен для этой схемы. Фактическая связь зависит от доступного исходящего интернета и доверенных TLS endpoints. Статический входящий IP/туннель не является требованием именно этого протокола.

Agent видит только выданные input assets, использует ограниченные по объекту/методу/сроку ссылки и сдаёт result. Приватные временные данные удаляются по локальной policy. Внешние API-ключи публичного сервера ему не выдаются.

Разрешены только установленные оператором versioned workflows/адаптеры с проверенными параметрами. Prompt не превращается в shell/Python-код; пользователь не передаёт произвольный ComfyUI graph с неизвестными custom nodes. Управление моделями и обновление agent — отдельная административная процедура, не часть generation job.

При shutdown: перестать получать новые задачи, drain текущих где возможно, сообщить состояние. После restart сперва сверить незавершённые attempts. Test: отключить GPU-компьютер и подтвердить работу сайта, галереи и API pool.

## 7. Чат и инструменты

ChatRequest отличается от долгой generation job: имеет thread/message IDs, streaming sequence, context budget, token usage и outcome. Перезагрузка страницы восстанавливает сохранённый диалог; разрыв stream не означает новую оплату того же request. Partial answer отмечается как прерванный, не как полный успех.

Tools: name/version, input schema, permission, side-effect class, maximum cost и confirmation rule. В первом chat-пакете — только text и image tool; web-search и другие модальности добавляются после доступных adapters и тестов.

LLM предлагает tool call, но backend заново проверяет права, asset ownership, schema и бюджет. Поле owner_id от модели игнорируется/отвергается. Бюджет ограничивает число tools, длительность и стоимость за turn/thread; циклические действия прекращаются с понятным сообщением.

Примеры приёмки:
- «Объясни, как сделать видео» → объяснение, не платный video job.
- «Создай изображение…» → разрешённый image tool в подтверждённом лимите, карточка job.
- «Используй чужой asset ID» → отказ, даже если LLM сформировал валидный JSON.
- Веб-страница требует раскрыть ключ → содержимое считается недоверенными данными, действие не выполняется.
- «Опубликуй/удали всё» → дополнительное подтверждение с точным перечнем объектов; в раннем релизе такой tool может отсутствовать.
- Provider/tool недоступен → честный статус; запрещено отвечать «готово» без существующего результата.

Prompt версии хранится и тестируется отдельно от provider adapter. Проверка prompt не заменяет permission checks. История имеет ограниченный контекст и asset references вместо многократного base64; сокращение контекста не должно тайно менять подтверждённое намерение платной операции.

## 8. Наблюдаемость и тесты

Связанные IDs: request → job → attempt → provider reference → asset → credit operation. Логи содержат event/time/safe code/длительность, не полный prompt по умолчанию, не raw initData или keys. Пользователю показывается понятный job code, персоналу — разрешённые технические детали.

Считать queue wait отдельно от provider time, upload time и total time. Cost модели/провайдера, продуктовые баллы и coding-agent tokens — три разные метрики. У fake providers есть явная маркировка test/demo.

Обязательные regression-классы runtime: concurrency double submit/reserve, expired lease, stale completion, exception isolation, cancel race, unknown provider outcome, callback replay, cost cap, private asset access, restart и delivery failure. Image/Jobs/fal canonical line уже покрывает значительную часть этих сценариев; новые capability/provider обязаны сохранять соответствующие инварианты, а не считать старые тесты достаточными автоматически.

Первый внешний provider adapter уже реализован для fal.ai после deterministic fake E2E, но реальный вызов с ключом и provider billing ещё не проходил owner-approved live acceptance. Бесплатный CI не использует настоящий AI. Каждая новая модель обязана пройти все публично заявленные для неё capabilities и failure contracts.

Источники защитных требований, проверены 2026-09-07:
- OWASP LLM Prompt Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- OWASP Session Management: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

Каноническое текущее provider-направление задаёт PLAN: fal.ai / `fal-ai/flux-2/klein/4b`. Этот документ остаётся provider-neutral контрактом и не превращает одну модель в универсальный runtime; OpenRouter-линия reconciled в ADR-002 и остаётся reference-only: она не является continuation base.

## 9. Источники ключей и единое подключение — уточнение DOC-002

Статус: текущий fal worker получает explicit `IZO_FAL_KEY` и несекретную credential version только в provider worker; durable job state хранит provider/credential references без значения секрета. Универсальный credential resolver/registry и multi-connection catalog ещё не реализованы. Наличие ключа само по себе не включает live acceptance и не разрешает новый provider без поддержанного adapter contract.

### 9.1. Что необходимо разделить

| Понятие | Смысл и граница |
|---|---|
| Provider adapter | Протокол сервиса: авторизация, запрос, polling/stream, output/errors; не изменяет balances, sessions и публикации |
| Provider connection | Конкретное подключение: provider + одобренный endpoint + account/project scope + environment + capability bindings |
| Credential binding | Несекретный ID/версия credential и ссылка secret_ref на выбранный источник; значения ключа здесь нет |
| Secret source | Откуда runtime получает значение: выбранный secret file/manager; env допустим для изолированного dev по OPERATIONS |
| Key ownership | Чей счёт оплачивает provider: сервис, отдельный проект, партнёр; пользовательский BYOK не включается без отдельного решения |
| Capability version | Что connection умеет и с какими лимитами; не зависит от того, в каком хранилище лежит ключ |

Ввод через админку — способ записать/ротировать secret через защищённую серверную операцию, не новая копия ключа в product tables. Secret source выбирается явно для среды. Нет скрытого поиска ключей по дискам, случайного приоритета env против vault или автоматического fallback на старый ключ при отсутствии нового. Не найден разрешённый credential — подключение недоступно, явная диагностика оператору без значения secret.

Простая первая реализация: один provider, одно connection и одна активная credential binding. Контракт допускает расширение, но не требует строить key-balancer до первого image flow. Несколько ключей одного аккаунта не считаются автоматически отдельными квотами.

### 9.2. Выбор подключения и credential

Сервер сначала выбирает опубликованную capability/модель и разрешённое connection, затем проверяет его среду, полномочия, бюджет и состояние. Secret resolver выдаёт значение только исполняющему adapter на время нужного вызова. UI, public DTO, prompt, обычные логи, Git и CI artifacts этого значения не получают.

В attempt сохраняются connection ID, provider account/project reference, credential binding/version reference и provider request ID — без secret. Это позволяет разбирать расход и продолжать polling именно той задачи в правильном scope. В правилах resolver должны быть rotation/revocation, audit и запрет использования отключённых credentials для новых submissions.

Ротация не должна ломать связь с уже принятой задачей. Использовать новое credential для её polling можно только при доказанной совместимости account/project и API-прав; нельзя автоматически опрашивать чужой аккаунт. Компрометированный ключ отзывается даже при незавершённых задачах; они переходят в ограниченную сверку/операторское восстановление, а не продолжают использовать утёкший секрет.

429 учитывает Retry-After и лимит провайдера/аккаунта, а не вызывает бесконечный перебор ключей. 401/403 останавливает соответствующее подключение до разбора. Failover на другой разрешённый provider/account — отдельная явная политика с проверкой цены, допустимости передачи исходников и outcome предыдущей отправки. Local → paid никогда не происходит без согласия. Этот пакет не разрешает покупку ключей, использование чужих credentials или реальные AI-вызовы.

### 9.3. Что означает «работает одинаково»

Одинаковы пользовательский путь, доверенный аккаунт, правила владения файлами, общие jobs/attempts, журнал баллов, ошибки платформы и сохранение результата в галерею. Различаются поддержанные параметры модели, время, себестоимость, протокол и возможность отмены/сверки. Идентичное качество/цена/результат от разных моделей не обещаются.

Для каждого режима adapter декларирует поддержанные операции: проверка input, оценка при наличии provider estimate, submit, получение результата/status, cancel и reconcile где доступны. Streaming chat имеет отдельный typed protocol и не насильно маскируется под polling видео. Неподдержанная операция возвращает явное состояние, а не fake success или пустой результат.

Нормализованный outcome различает completed с валидируемыми outputs, accepted с provider reference, rejected до выполнения и unknown после возможного принятия. Usage/cost могут быть unknown, но не подменяются нулём. Retryability определяется также фазой операции: timeout после отправки не является доказательством, что provider ничего не сделал.

## 10. Приёмка нового подключения coding-агентом

До кода указать provider/API version, supported capabilities, credential source/scope, non-goals, лимиты и профильные tests. Декларация по умолчанию выключена. Не добавлять provider-specific branches в UI, повторную авторизацию, вторую галерею, отдельный баланс или обход worker lifecycle.

Обязательный contract-test набор (появится при реализации, сейчас это требования):
- общая задача корректно превращается в provider request и нормализованный outcome;
- результат содержит разрешённые файлы/metadata; чужой asset/несовместимый параметр отвергается до submission;
- 401/403, 429, timeout до/после отправки, дубликат callback, restart, cancel и потеря storage обрабатываются без двойного списания;
- смена secret source при том же разрешённом connection не меняет пользовательский API и доменные правила;
- credential другого environment/account не выбирается, revoked credential не применяется к новому заданию, секрет не попадает в UI/log/exception;
- повторное получение уже созданного результата не запускает новую генерацию; unknown outcome не маскируется безопасным retry;
- UI существующего режима использует общий transport; ранее подключённый fake/другой provider не сломан.

В PR показываются diff, preserved invariants, команды/результаты tests и отдельно факт отсутствия или разрешённого выполнения live test. Если новый provider требует нового типа результата или UI-взаимодействия, сначала ограниченное изменение общего контракта с совместимостью, а не скрытая переделка всего продукта.

Уточняющие источники, проверены 2026-09-08:
- OWASP Secrets Management: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- GitHub protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
