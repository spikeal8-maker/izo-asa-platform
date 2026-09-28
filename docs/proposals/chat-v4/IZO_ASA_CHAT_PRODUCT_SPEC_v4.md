# IZO ASA Platform — Chat Product Specification v4

**Статус:** кандидат на каноническое продуктовое ТЗ Chat. После подтверждения владельцем должен заменить узкую конечную цель `TEXT_CHAT_V1_ACCEPTED` в Issue #222 и стать источником приоритета для Chat-связанных owner issues.  
**Тип документа:** стабильное продуктовое ТЗ. Не хранит текущие SHA, PR, working branch или next package.  
**Главный результат:** `CHAT_PRODUCT_V1_ACCEPTED`.

---

## 1. Цель

IZO ASA Chat — основное универсальное AI-рабочее место платформы. Пользователь ведёт один многошаговый разговор, выбирает доступную ему модель, получает качественно оформленные ответы, прикладывает изображения и файлы, просит анализировать их, создаёт реальные скачиваемые документы и изображения, продолжает редактирование результатов в том же диалоге и возвращается к разговору после перезагрузки или перезапуска приложения.

Chat должен быть функционально сопоставим с лучшими пользовательскими паттернами современных ChatGPT/Claude-класса систем, но оставаться визуально и архитектурно продуктом IZO ASA. Внешние продукты являются источником исследовательских референсов, а не живой нормативной спецификацией: после выбора поведения оно фиксируется в этом ТЗ и меняется только отдельным продуктовым решением.

### Нормативная модальность

- **MUST** — обязательное условие соответствующего acceptance gate.
- **SHOULD** — сильное требование; отклонение допускается только с зафиксированной причиной и без нарушения цели.
- **MAY** — допустимое расширение, не являющееся blocker.
- **DEFERRED** — сознательно отложено за пределы Chat Product V1.

---

## 2. Что является Chat Product V1

Chat Product V1 — не «работающий API» и не «Markdown-страница». Он состоит из пяти последовательно принимаемых продуктовых уровней.

| Уровень | Результат | Блокирует следующий уровень |
| --- | --- | --- |
| P1 — Conversation Experience | Надёжный разговор, контекст, история, renderer, actions | Да |
| P2 — Multimodal Input | Изображения и основные документы/таблицы/аудио как вход | Да |
| P3 — Creation & Tools | Реальные создаваемые файлы + генерация/редактирование изображений | Да |
| P4 — Product Control | Provider abstraction, Admin model policy, доступы и расход | Да |
| P5 — Release Acceptance | Security/performance/a11y/restart/clean package/live acceptance | Да |

`CHAT_PRODUCT_V1_ACCEPTED` разрешён только после P1–P5. Это не означает, что каждый уровень должен быть одним PR: уровень может состоять из нескольких bounded packages.

Крупные новые направления Video generation, Audio/TTS generation, 3D generation и autonomous agents не должны вытеснять незакрытые blocker P1–P5.

---

## 3. Пользовательская композиция

Верхняя панель, навигация, темы и фирменные цвета остаются IZO ASA. Chat содержит:

1. историю диалогов / поиск / новый чат;
2. поток сообщений;
3. composer;
4. model selector;
5. attachment/context picker;
6. контекстные действия сообщений и результатов.

### Требования

- **CHAT-P-UI-001 [MUST/P1]** — Desktop использует читаемую ограниченную prose-колонку; широкие таблицы, код и медиа могут быть шире, но не создают document-level horizontal overflow.
- **CHAT-P-UI-002 [MUST/P1]** — Phone остаётся одноколоночным; history — drawer/sheet; composer не прячется под виртуальной клавиатурой и учитывает safe-area.
- **CHAT-P-UI-003 [MUST/P1]** — Пустой Chat показывает heading + composer как единый стартовый блок; активный Chat сохраняет composer доступным внизу.
- **CHAT-P-UI-004 [MUST/P1]** — Все действия доступны мышью, touch и клавиатурой; hover не является единственным способом доступа.
- **CHAT-P-UI-005 [SHOULD/P1]** — История на desktop может иметь compact/expanded режим, если это не ухудшает чтение и accessibility.

---

## 4. P1 — Conversation Experience


### 4.1. Разговор и история

- **CHAT-P-LIFE-001 [MUST/P1]** — Разговор, сообщения и request-state сохраняются сервером; localStorage не является source of truth истории.
- **CHAT-P-LIFE-002 [MUST/P1]** — Reload/reconnect возвращает существующий разговор и не создаёт новый provider call для уже принятого request.
- **CHAT-P-LIFE-003 [MUST/P1]** — Один пользовательский submit имеет стабильный request identity и idempotent replay semantics.
- **CHAT-P-LIFE-004 [MUST/P1]** — Stop является серверной командой; закрытие fetch/SSE в браузере не считается доказанным Stop.
- **CHAT-P-LIFE-005 [MUST/P1]** — Unknown/interrupted outcome отображается честно; blind retry платного/неопределённого запроса запрещён.
- **CHAT-P-LIFE-006 [MUST/P1]** — История поддерживает cursor pagination, новый чат, поиск, rename, archive и restore.
- **CHAT-P-LIFE-007 [MUST/P1]** — Regenerate выполняется в текущей active Branch и создаёт новый AssistantAttempt + ChatRequest для того же immutable UserMessage. `active_branch_id` не меняется; предыдущий selected attempt остаётся selected во время pending/streaming. Только durable `COMPLETED` атомарно переключает persisted selection на новый attempt. `ERROR`/`STOPPED`/`INTERRUPTED` сохраняют прежний selection; `UNKNOWN` также сохраняет его и блокирует новое execution до reconciliation, после которого доказанный `COMPLETED` переключает selection, а no-execution/rejected/error — нет.
- **CHAT-P-LIFE-008 [MUST/P1]** — Edit user message не изменяет прежние Branch/UserMessage: создаются descendant Branch с явной fork-reference и новый immutable UserMessage. После успешного создания descendant Branch `thread.active_branch_id` автоматически переключается на неё. Новая Branch наследует selected-attempt mapping родителя только для prefix до fork point; для edited turn selection изначально `NONE`, и старый parent answer после fork не выбирается автоматически. Durable `COMPLETED` нового edited-turn attempt становится selected; `ERROR`/`STOPPED`/`INTERRUPTED` оставляют `NONE`; `UNKNOWN` оставляет `NONE` и блокирует новое execution до reconciliation.
- **CHAT-P-LIFE-009 [MUST/P1]** — UI и Context Engine используют только server-owned persisted `active_branch_id` и selected AssistantAttempt mapping. Явный выбор Branch атомарно меняет `active_branch_id` и использует собственную persisted mapping этой Branch; явный выбор alternative attempt разрешён только для `COMPLETED` attempts и атомарно меняет selection. Timestamp, DOM order и «последний streamed attempt» не являются authority; reload/restart восстанавливает тот же state.
- **CHAT-P-LIFE-010 [MUST/P1]** — Retry является recovery-действием, а не синонимом Regenerate. Known pre-submit failure повторяет тот же request identity/fingerprint и тот же AssistantAttempt: active Branch/previous selection не меняются во время retry, durable `COMPLETED` выбирает текущий candidate attempt, а `ERROR`/`STOPPED`/`INTERRUPTED` не заменяют прежний/`NONE` selection; `UNKNOWN` требует reconciliation. Known post-submit safe failure, где доказано no billable/provider execution, создаёт новый ChatRequest + AssistantAttempt с `retry_of_request_id` и использует те же selection transitions, что Regenerate.
- **CHAT-P-LIFE-011 [MUST/P1]** — Обычное продолжение разговора означает новый UserMessage в active Branch. Отдельная кнопка «Continue generating» не является P1 blocker и не вводится без собственного request/attempt lifecycle contract.


### 4.2. Context Engine

Chat сохраняет полную историю и отдельно строит ограниченный execution-context для конкретного resolved model snapshot.

- **CHAT-P-CTX-001 [MUST/P1]** — Context builder использует только active Branch и выбранные terminal AssistantAttempts; failed/unknown/partial не выдаются модели как подтверждённая assistant truth без явной recovery policy.
- **CHAT-P-CTX-002 [MUST/P1]** — Переключение модели внутри диалога не уничтожает историю. Перед каждым submit заново проверяются context limit, modality/tool compatibility, effective access и billing eligibility.
- **CHAT-P-CTX-003 [MUST/P1]** — При меньшем context window новой модели сервер детерминированно сокращает только execution-context; persisted history не переписывается и не удаляется.
- **CHAT-P-CTX-004 [MUST/P1]** — Context budget резервирует output budget и считает текст, structured sources, file excerpts, attachments и tool results по model-specific tokenizer либо по versioned conservative estimator с safety margin; выбранный calculator/version входит в execution snapshot.
- **CHAT-P-CTX-005 [SHOULD/P1]** — Для длинных разговоров допускается server-owned summarization/reduction, но summary не заменяет исходную историю.
- **CHAT-P-CTX-006 [MUST/P1]** — Нормативный selection order: mandatory System/Product policy → current UserMessage и обязательные зависимости текущего turn → selected terminal AssistantAttempts и связанные turns от новых к старым → versioned summary/reduction старого допустимого prefix. Если mandatory set + reserved output не помещаются, request отклоняется до provider call.
- **CHAT-P-CTX-007 [MUST/P1]** — Summary имеет identity/version, source-range/provenance и policy-version. Он invalidated, если Edit/Branch меняет его source prefix, меняется selected attempt внутри source range, меняется referenced tool/file/source result либо policy-version требует rebuild.
- **CHAT-P-CTX-008 [MUST/P1]** — Current-turn attachment/tool requirement нельзя молча отбросить при switch на incapable model: admission блокируется либо предлагает compatible effective model. Historical unsupported binary/provider payload не передаётся новой модели; допускаются только поддержанные normalized derived text/evidence с provenance.
- **CHAT-P-CTX-009 [MUST/P1]** — Обязательные fixtures включают `128k → 32k`, vision-capable → text-only, tool-capable → tool-incapable и смену provider. Во всех случаях history сохраняется, context selection и отказ/сокращение воспроизводимы по одному policy-version.

### 4.3. Response Formatting Contract

Любая conversation-модель получает IZO-owned правила оформления ответа. Цель — одинаково качественная структура независимо от DeepSeek/OpenRouter/будущего провайдера.

- **CHAT-P-FMT-001 [MUST/P1]** — Модель инструктируется использовать Markdown только там, где он улучшает читаемость: заголовки, списки, таблицы, code fences, inline code, blockquotes и формулы.
- **CHAT-P-FMT-002 [MUST/P1]** — Code fence должен содержать язык, если он известен; обычная проза не должна помещаться в code block ради оформления.
- **CHAT-P-FMT-003 [MUST/P1]** — Таблицы используются для сравнительных/структурированных данных, а не автоматически для любого списка.
- **CHAT-P-FMT-004 [MUST/P1]** — Модель не должна выдавать raw HTML/JS как механизм оформления обычного ответа.
- **CHAT-P-FMT-005 [MUST/P1]** — Обычная модельная ссылка не считается проверенной citation без структурированного evidence от системы.
- **CHAT-P-FMT-006 [SHOULD/P1]** — Emoji и визуальные маркеры сохраняются, когда семантически полезны, но не навязываются стилем платформы.

### 4.4. Renderer

Renderer принадлежит IZO ASA, а не модели или provider.

| Контент | Требование P1 |
| --- | --- |
| Абзацы | корректные интервалы, переносы, Unicode |
| Headings | H1–H6 с устойчивой визуальной иерархией |
| Emphasis | bold, italic, strike |
| Lists | ordered/unordered/nested/task lists |
| Quote | визуально отдельный blockquote |
| Inline code | отдельная monospace presentation |
| Fenced code | язык, syntax highlight, Copy exact source |
| Tables | GFM table, семантика, внутренний horizontal scroll |
| Math | inline + display presentation |
| Links | allowlisted safe schemes, external handling |
| Streaming | незакрытые Markdown/code/math не ломают сообщение |

- **CHAT-P-RENDER-001 [MUST/P1]** — Raw HTML отключён; `javascript:` и аналогичные unsafe links не исполняются.
- **CHAT-P-RENDER-002 [MUST/P1]** — External Markdown images не загружаются автоматически без отдельной source/media policy.
- **CHAT-P-RENDER-003 [MUST/P1]** — Длинный code/table блок скроллится внутри себя и не растягивает страницу.
- **CHAT-P-RENDER-004 [MUST/P1]** — Split UTF-8, незакрытые emphasis/code fence/table/math при streaming не приводят к XSS, падению UI или повреждению final content.
- **CHAT-P-RENDER-005 [MUST/P1]** — Final render и render после reload семантически эквивалентны исходному сохранённому Markdown/parts.
- **CHAT-P-RENDER-006 [MUST/P1]** — Автопрокрутка следует за потоком только пока пользователь находится у конца; чтение старого текста не перехватывается.


### 4.5. Actions и clipboard

- **CHAT-P-ACT-001 [MUST/P1]** — Assistant message имеет Copy, Copy Markdown и Regenerate; branch/attempt selector/action доступен, когда у turn есть альтернативы.
- **CHAT-P-ACT-002 [MUST/P1]** — User message имеет Copy и Edit-as-new-branch.
- **CHAT-P-ACT-003 [MUST/P1]** — Code/config block имеет отдельный Copy exact source без визуального toolbar, line numbers или normalization содержимого.
- **CHAT-P-ACT-004 [MUST/P1]** — Copy whole answer сериализует normalized message model, а не DOM: всегда `text/plain`, а rich-capable browser также получает sanitized `text/html` без toolbar/button/hidden UI.
- **CHAT-P-ACT-005 [MUST/P1]** — Copy Markdown возвращает canonical Markdown как `text/markdown` и `text/plain` fallback; serialized source не зависит от текущего DOM/render library.
- **CHAT-P-ACT-006 [SHOULD/P1]** — Таблица может дополнительно предлагать «Copy table»/CSV export, если это не усложняет основной renderer.
- **CHAT-P-ACT-007 [SHOULD/P1]** — Feedback может быть добавлен отдельным bounded contract. До определения storage/privacy/abuse semantics он не блокирует P1.

## 5. Composer

- **CHAT-P-COMP-001 [MUST/P1]** — Базовая композиция: `+`, textarea, model selector, mic, send/stop. Постоянный каталог внутренних tools в composer запрещён.
- **CHAT-P-COMP-002 [MUST/P1]** — Enter отправляет, Shift+Enter добавляет строку; IME composition не вызывает случайный submit.
- **CHAT-P-COMP-003 [MUST/P2]** — Выбранные attachments отображаются до отправки; порядок стабилен.
- **CHAT-P-COMP-004 [MUST/P2]** — Если текущая модель не принимает выбранную modality, Chat предлагает совместимую разрешённую модель или явное удаление attachment; молча игнорировать файл запрещено.
- **CHAT-P-COMP-005 [MUST/P1]** — Model selector показывает только effective model choices пользователя и реально участвует в request fingerprint/execution snapshot.
- **CHAT-P-COMP-006 [MUST/P1]** — Auto model допустим только как server-owned policy; browser не придумывает маршрут самостоятельно.

---

## 6. P2 — Multimodal Input

### 6.1. Принцип

«Chat принимает файлы» означает: поддержанный файл можно загрузить как private owned asset; система валидирует тип и выбирает разрешённый parser/capability. Неизвестный формат может быть сохранён/скачан, но не выдаётся за успешно проанализированный.


### 6.2. Обязательный входной набор P2

P2 support описывается по операциям, а не фразой «формат поддерживается». `MUST card` означает безопасную file-card presentation; `P3` означает, что операция не является P2 blocker.

| Формат | Upload | Store | Preview P2 | Extract P2 | Analyze P2 | Edit | Generate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PNG/JPEG/WebP | MUST | MUST | MUST inline | metadata MAY | MUST через effective vision path | P3 image-edit | P3 |
| PDF | MUST | MUST | MUST card; page preview MAY | MUST pages/text/structure | MUST | DEFERRED | P3 |
| DOCX | MUST | MUST | MUST card | MUST paragraphs/tables/relationships | MUST | DEFERRED | P3 |
| XLSX | MUST | MUST | MUST card | MUST workbook/sheet/range/formula facts | MUST | DEFERRED | P3 |
| CSV/TSV | MUST | MUST | MUST card | MUST rows/columns with bounded typing | MUST | DEFERRED | P3 |
| TXT/MD | MUST | MUST | MUST card; safe text preview MAY | MUST text | MUST | DEFERRED | P3 |
| HTML | MUST | MUST | MUST card; active preview запрещён | MUST sanitized text/structure | MUST | DEFERRED | P3 |
| JSON | MUST | MUST | MUST card | MUST bounded parsed structure | MUST | DEFERRED | P3 |
| XML/YAML | MUST | MUST | MUST card | MUST safe bounded parsed structure | MUST | DEFERRED | P3 |
| Source files allowlist | MUST | MUST | MUST card; safe text preview MAY | MUST text/metadata | MUST | DEFERRED | P3 |
| Audio: минимум один browser-friendly format | MUST | MUST | MUST safe player/card | MUST ASR transcript + segments | MUST по transcript/approved audio capability | DEFERRED | post-V1 generation |
| Video | SHOULD | SHOULD | SHOULD metadata/card | metadata SHOULD | deep analysis DEFERRED | DEFERRED | DEFERRED |

Video upload/store/metadata не блокирует P2: он становится отдельным bounded package, если у Chat Core появляется подтверждённый use-case.

- **CHAT-P-FILE-001 [MUST/P2]** — Attachment identity — `asset_id`; base64/object key/provider URL не являются identity сообщения.
- **CHAT-P-FILE-002 [MUST/P2]** — Picker/paste/drop используют единую server-owned validation pipeline и одинаковые лимиты.
- **CHAT-P-FILE-003 [MUST/P2]** — Image получает inline preview; другие P2 files получают file card с именем, trusted type/status, размером и доступным action.
- **CHAT-P-FILE-004 [MUST/P2]** — Preview/download после reload проходит через authenticated Media delivery.
- **CHAT-P-FILE-005 [MUST/P2]** — PDF/DOCX/XLSX/CSV и остальные форматы, помеченные MUST Extract в matrix, имеют валидированный extraction path; структура не превращается без необходимости в один неразмеченный текст.
- **CHAT-P-FILE-006 [MUST/P2]** — Audio проходит через принятую ASR capability и сохраняет transcript ↔ source asset/segment provenance.
- **CHAT-P-FILE-007 [MUST/P2]** — Unsupported analysis показывает честное состояние «файл загружен, анализ этого формата пока недоступен».
- **CHAT-P-FILE-008 [MUST/P2]** — Extracted context сохраняет provenance как минимум до asset и применимой page/sheet/range/section/segment координаты.
- **CHAT-P-FILE-009 [MUST/P2]** — Extension, filename и browser `Content-Type` считаются untrusted metadata. Server определяет trusted actual format по bounded allowlisted detection; declared/actual mismatch либо отклоняется, либо безопасно нормализуется. Parser выбирается только по server-owned detected type; parser/extractor network/external-resource fetch default-deny.

### 6.3. Sources/citations

- **CHAT-P-SRC-001 [MUST/P2]** — Системная citation из файла/поиска является структурированным evidence-object, а не строкой `[1]`, придуманной моделью.
- **CHAT-P-SRC-002 [MUST/P2]** — PDF evidence может ссылаться на page; spreadsheet evidence — на sheet/range; audio — на временной segment, когда extractor это поддерживает.
- **CHAT-P-SRC-003 [MUST/P2]** — Обычная внешняя ссылка модели визуально отличается от verified source evidence.

---

## 7. P3 — Creation & Tools

### 7.1. Generated files

Chat обязан возвращать реальный downloadable asset. Фраза «я создал файл» без файла — failure.

**Обязательный P3 output set:** PDF, DOCX, XLSX, CSV/TSV, HTML, Markdown/TXT, JSON.  
**PPTX:** SHOULD до финального Product V1, но может быть отдельным bounded package, если не блокирует основные документы.

- **CHAT-P-GEN-001 [MUST/P3]** — Generated file создаётся server-side tool/runtime и сохраняется через shared Media/File delivery.
- **CHAT-P-GEN-002 [MUST/P3]** — File card показывает тип, имя, размер, Open/Preview при безопасной поддержке и Download.
- **CHAT-P-GEN-003 [MUST/P3]** — «Измени созданный файл» создаёт новую версию/derived asset; старая версия не исчезает автоматически.
- **CHAT-P-GEN-004 [MUST/P3]** — XLSX acceptance проверяет структуру workbook/sheets/formulas там, где они запрошены, а не только расширение файла.
- **CHAT-P-GEN-005 [MUST/P3]** — HTML preview sandboxed; generated HTML не получает доступ к session secrets/host APIs.

### 7.2. Artifacts

В Product V1 **Generated File** обязателен. Полноценный отдельный rich editor уровня стороннего Canvas/Artifacts не является blocker.

- **CHAT-P-ART-001 [MUST/P3]** — Artifact V1 означает versioned logical result, способный ссылаться на одну или несколько версий Media/file output.
- **CHAT-P-ART-002 [SHOULD/P3]** — Text/HTML/code artifact может иметь встроенный preview/editor, если это не превращает P3 в отдельную офисную платформу.
- **CHAT-P-ART-003 [DEFERRED]** — Полный универсальный collaborative document editor не входит в Chat Product V1.

### 7.3. Изображения

- **CHAT-P-IMG-001 [MUST/P3]** — User может запросить image generation обычным сообщением; Chat показывает Job/processing и terminal ImageResult, а не fake success.
- **CHAT-P-IMG-002 [MUST/P3]** — Generated image открывается в Chat viewer/fullscreen, скачивается и может использоваться в следующем сообщении.
- **CHAT-P-IMG-003 [MUST/P3]** — Текстовая команда редактирования создаёт новую derived image version с provenance к исходнику.
- **CHAT-P-IMG-004 [MUST/P3]** — Если image operation платная/неоднозначная, применяется server quote/confirmation policy.
- **CHAT-P-IMG-005 [SHOULD/P3]** — Region/mask editing MAY быть отдельным package после text-based edit без изменения asset-version contract.

---

## 8. P4 — Models, Providers, Admin и расход

### 8.1. Conversation models

- **CHAT-P-MODEL-001 [MUST/P4]** — Chat frontend не знает provider-specific transport. Он получает нормализованный effective model catalog.
- **CHAT-P-MODEL-002 [MUST/P4]** — DeepSeek и OpenRouter поддерживаются текущей линией; будущий provider добавляется адаптером без нового renderer/history/billing implementation.
- **CHAT-P-MODEL-003 [MUST/P4]** — Discovery provider не публикует модель пользователям автоматически.
- **CHAT-P-MODEL-004 [MUST/P4]** — Переключение модели в существующем thread перепроверяет context/modality/price/access перед submit.


### 8.2. Admin

Администратор управляет продуктовой публикацией, а не просто «видит список API моделей».

Минимальный workflow:

`Provider discovery/config → candidate → product model → capabilities → display name → price/billing policy → plan/user access → publish/disable/retire → audit`.

- **CHAT-P-ADMIN-001 [MUST/P4]** — Admin может включать/выключать/retire product model без удаления исторических ссылок.
- **CHAT-P-ADMIN-002 [MUST/P4]** — Admin задаёт доступ по plan и, при необходимости, explicit account override.
- **CHAT-P-ADMIN-003 [MUST/P4]** — Admin задаёт user-visible price/billing policy независимо от provider-reported raw cost.
- **CHAT-P-ADMIN-004 [MUST/P4]** — Финансовые и privilege изменения имеют immutable audit trail и scoped permissions.
- **CHAT-P-ADMIN-005 [MUST/P4]** — Effective availability вычисляется ровно одной server-side authority. Hard-deny envelope: retired/disabled/unpublished product model, restricted account, unavailable provider/credential, incompatible capability/modality и billing-ineligible state запрещают admission и не могут быть преодолены user override, plan override или frontend state. Plan/account override может только дополнительно сузить/разрешить доступ внутри глобально published+enabled envelope; frontend получает готовую effective projection, а не вычисляет её.


### 8.3. Daily allowance и Premium balance

В продукте есть два пользовательских ресурса, но это не означает заранее две физические таблицы ledger.

- **Daily allowance** — периодически выдаваемый/сбрасываемый ресурс по plan policy.
- **Premium balance** — сохраняемый пополняемый баланс для premium operations.

Server Spend Authority возвращает логический `FundingPlan`:

```text
FundingPlan
├─ sources[]              # resource + authorized/reserved amount
├─ settlement_rule
├─ confirmation_required
├─ provider_payer         # platform | user | none
└─ platform_fee           # explicit separate line item or none
```

Нормативные политики:

| Policy | Funding semantics |
| --- | --- |
| `FREE` | Нет Daily/Premium debit, platform funding reservation и billable provider/runtime charge для этой operation; если внешний расход несёт платформа, policy = `PLATFORM_FUNDED`. |
| `PLATFORM_FUNDED` | Provider/runtime cost оплачивает платформа; user Daily/Premium не списываются. |
| `DAILY_ONLY` | Daily должен покрывать всю product price; иначе deny. |
| `PREMIUM_ONLY` | Premium reservation покрывает всю product price. |
| `DAILY_THEN_PREMIUM` / `DAILY_FIRST` | Daily расходуется первым, Premium покрывает ровно shortfall. Пример: daily=3, price=5 → reserve/claim daily 3 + premium 2. Premium shortfall требует quote/confirmation, если нет явной user opt-in policy. |
| `MIXED` | Разбиение источников заранее задаётся versioned product policy/quote; browser/model не придумывают split. Любая Premium часть проходит свою confirmation policy. |
| `BYOK` | `provider_payer=user`; provider charge идёт на credential/account пользователя. Daily/Premium debit по умолчанию отсутствует. Допустимый `platform_fee` — отдельная явно показанная строка с собственным FundingPlan; он не маскируется под provider cost. |

Для всех non-FREE policies admission выполняет атомарный authorize/claim-or-reserve всех требуемых user resources либо ничего. Settle фиксирует доказанный фактический product charge в пределах принятого quote/policy; release освобождает неиспользованный reserve/claim по правилам соответствующего resource. Unknown external outcome удерживает затронутые provisional claims/reservations в reconcile state и запрещает blind retry до разрешения outcome; нулевой cost не подставляется вместо unknown.

- **CHAT-P-SPEND-001 [MUST/P4]** — Server Spend Authority атомарно решает admission и формирует FundingPlan; Chat UI, provider adapter и модель не выбирают источник средств.
- **CHAT-P-SPEND-002 [MUST/P4]** — Поддерживаются минимум `FREE`, `PLATFORM_FUNDED`, `DAILY_ONLY`, `PREMIUM_ONLY`, `DAILY_THEN_PREMIUM/DAILY_FIRST`, `MIXED`, `BYOK` с semantics из таблицы.
- **CHAT-P-SPEND-003 [MUST/P4]** — `DAILY_THEN_PREMIUM` использует normative split daily-first + premium-shortfall и quote/confirmation перед Premium shortfall без user opt-in.
- **CHAT-P-SPEND-004 [MUST/P4]** — `BYOK` не создаёт скрытый Premium debit. Любой platform fee отделён от provider cost, показан до execution и проходит собственную funding/confirmation policy.
- **CHAT-P-SPEND-005 [MUST/P4]** — Paid/platform-funded execution использует stable operation/request ID и соответствующие resource primitives `reserve/claim → settle/release → reconcile`; existing Credits reserve/settle/release сохраняются, а persistence Daily выбирается ADR.
- **CHAT-P-SPEND-006 [MUST/P4]** — Provider input/output tokens/cost facts не называются пользовательскими credits.
- **CHAT-P-SPEND-007 [MUST/P4]** — UI показывает Daily allowance и Premium balance раздельно, показывает provider payer/platform fee где применимо и не обещает нулевую стоимость при unknown outcome.

## 9. P5 — Release Acceptance

### 9.1. Security/product trust

- **CHAT-P-SEC-001 [MUST/P5]** — Account A не получает private Thread/Message/File/Image/Credential Account B без отдельного share/public contract.
- **CHAT-P-SEC-002 [MUST/P5]** — Контент загруженных документов, web/tool outputs и metadata считается untrusted data и не может повышать privileges, менять system/product policy или разрешать tool execution.
- **CHAT-P-SEC-003 [MUST/P5]** — Raw chain-of-thought/provider reasoning не является пользовательским output contract.
- **CHAT-P-SEC-004 [MUST/P5]** — Неподдержанный/опасный файл не исполняется автоматически.


### 9.2. Performance/accessibility

- **CHAT-P-NFR-001 [MUST/P5]** — Automated compatibility suite включает Chromium, Firefox и WebKit. Real compatibility target отдельно включает desktop Chrome/Edge, Firefox, Safari где есть поддерживаемая target environment, а также Android Chrome и iOS Safari. Реальный mobile acceptance проверяет virtual keyboard, safe area, composer, scroll, file picker, clipboard, download и attachments; viewport emulation не считается заменой real mobile browser proof. Недоступный обязательный target = `NOT_RUN/BLOCKED`, не `PASS`.
- **CHAT-P-NFR-002 [MUST/P5]** — Длинный thread не требует полного reparsing/re-render всего разговора на каждый token; platform/UI overhead измеряется отдельно от provider queue/TTFT/generation latency.
- **CHAT-P-NFR-003 [MUST/P5]** — Все controls имеют accessible name, keyboard navigation и visible focus в двух темах.
- **CHAT-P-NFR-004 [MUST/P5]** — 320/390/768/1024/1440/1920 являются обязательными geometry checkpoints; QHD/UHD — smoke, а не замена browser-engine/real-device matrix.
- **CHAT-P-NFR-005 [MUST/P1]** — До P1 acceptance владелец фиксирует benchmark profile и численные thresholds, необходимые для streaming Chat; до этого соответствующий performance evidence = `BLOCKED`, а не произвольный PASS. Profile обязан задавать baseline device class, browser, thread/message size, stream rate, measurement points и p95/p99 там, где percentile применим. Минимально измеряются input responsiveness during streaming, chunk→render overhead, large-thread open, scroll stability, large code/table render и memory/DOM growth. P5 повторно проверяет утверждённый profile на release matrix; thresholds нельзя выдумывать implementer-ом ради PASS.

### 9.3. Functional vs portable acceptance

Разделяются два статуса:

- `CHAT_PRODUCT_V1_ACCEPTED` — P1–P5 функционально/технически приняты на конкретном checkpoint.
- `CHAT_PORTABLE_RELEASE_ACCEPTED` — проверен переносимый Docker/package сценарий на чистой установке.

Для публичной/передаваемой поставки нужны оба статуса. Это позволяет честно зафиксировать: «продуктовая функция закончена, упаковка ещё нет».

---

## 10. End-to-end acceptance P1–P5

Минимальный человеческий сценарий:

1. Пользователь входит и открывает Chat.
2. Видит только разрешённые effective models.
3. Получает streaming ответ с headings, emphasis, nested/task lists, table, math и code block.
4. Копирует code exact source, весь ответ как rich/plain и отдельно Markdown.
5. Делает follow-up; модель использует активный контекст.
6. Переключает model; история сохраняется, context/modality перепроверяются.
7. Regenerate не уничтожает старый ответ; Edit user message создаёт новую branch.
8. Rename/archive/restore/search/pagination работают после reload/restart.
9. Прикрепляет image и получает vision-ответ.
10. Прикрепляет PDF и XLSX и получает анализ со structured provenance.
11. Прикрепляет audio и получает transcript/analysis через принятую ASR capability.
12. Просит создать PDF/DOCX/XLSX/HTML и получает реальные валидные файлы.
13. Просит изменить созданный файл и получает новую версию.
14. Просит сгенерировать изображение, открывает/скачивает его и делает conversational edit, получая derived version.
15. Admin отключает model — новый admission больше её не разрешает.
16. Daily/Premium/BYOK policy ведёт себя согласно выбранной server policy; unknown outcome не делает blind retry.
17. Account B не получает private данные Account A.
18. Backend/DB/storage restart не нарушает accepted conversation/assets/spend state.
19. Required CI/security/browser suites зелёные на exact checkpoint.
20. `NOT_RUN`/`BLOCKED` evidence не объявляется `PASS`.

---

## 11. Deferred после Chat Product V1

- Video generation.
- Audio/TTS generation.
- 3D generation/editor.
- Full web deep research/search, если владелец отдельно не повысит приоритет.
- Autonomous multi-agent execution.
- Full collaborative office/editor suite.
- Публичные share links для private conversations/artifacts, если не выделены отдельным package.

Архитектура P1–P5 обязана позволять эти расширения без смены базовых Message/Tool/Media contracts.

---

## 12. Definition of Done канонического Product Spec

- Требования имеют явную модальность и gate.
- Нет current SHA/PR/branch.
- Внешний продукт не является живой нормативной зависимостью.
- Пользовательский acceptance отделён от архитектурных implementation choices.
- Точные owner modules, импорты, file budgets, provider/tool boundaries и cadence обслуживания находятся в архитектурном/engineering contracts, а не дублируются здесь.