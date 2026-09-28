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
- **CHAT-P-LIFE-007 [MUST/P1]** — Regenerate создаёт новую assistant-attempt для той же пользовательской реплики и не уничтожает предыдущий ответ.
- **CHAT-P-LIFE-008 [MUST/P1]** — Edit user message создаёт новую ветвь разговора от точки редактирования. Исходная ветвь сохраняется.
- **CHAT-P-LIFE-009 [MUST/P1]** — UI явно знает активную ветвь/активную attempt; только она используется как обычное продолжение контекста.

### 4.2. Context Engine

Chat обязан сохранять полную историю и отдельно строить ограниченный execution-context для конкретной модели.

- **CHAT-P-CTX-001 [MUST/P1]** — Context builder использует только активную ветвь и выбранные terminal assistant attempts; failed/interrupted partial не выдаются модели как подтверждённые ответы без явной политики.
- **CHAT-P-CTX-002 [MUST/P1]** — Переключение модели внутри диалога не уничтожает историю. Перед каждым submit заново проверяются context limit, modality compatibility и доступность модели.
- **CHAT-P-CTX-003 [MUST/P1]** — При меньшем context window новой модели сервер сокращает execution-context, но не удаляет сохранённую историю.
- **CHAT-P-CTX-004 [MUST/P1]** — Context budget резервирует место под ответ и учитывает текст, структурированные источники, вложения и tool results.
- **CHAT-P-CTX-005 [SHOULD/P1]** — При необходимости длинные разговоры используют серверную summarization/reduction policy с provenance, но summary не заменяет исходную историю.

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

- **CHAT-P-ACT-001 [MUST/P1]** — Assistant message: Copy, Copy Markdown, Regenerate, feedback; branch/continue action доступно там, где поддержана ветка.
- **CHAT-P-ACT-002 [MUST/P1]** — User message: Copy и Edit-as-new-branch.
- **CHAT-P-ACT-003 [MUST/P1]** — Code/config block имеет отдельный Copy exact content.
- **CHAT-P-ACT-004 [MUST/P1]** — Copy whole answer формирует clipboard из нормализованного message, а не копирует DOM с toolbar/иконками. Минимум `text/plain`; rich-capable browser также получает чистый `text/html`.
- **CHAT-P-ACT-005 [MUST/P1]** — Copy Markdown возвращает канонический Markdown без UI-shell.
- **CHAT-P-ACT-006 [SHOULD/P1]** — Таблица может дополнительно предлагать «Copy table»/CSV export, если это не усложняет основной renderer.

---

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

| Класс | P2 minimum |
| --- | --- |
| Images | PNG, JPEG, WebP |
| Documents | PDF, DOCX, TXT, MD, HTML |
| Spreadsheets | XLSX, CSV, TSV |
| Structured text | JSON, XML, YAML |
| Source code | текстовые исходники по allowlist |
| Audio | минимум один browser-friendly upload format + ASR path |
| Video | upload/store/metadata обязательно; глубокий анализ MAY до отдельной video-analysis capability |
| Legacy/complex formats | MAY; не blocker P2 |

- **CHAT-P-FILE-001 [MUST/P2]** — Attachment identity — `asset_id`; base64/object key/provider URL не являются identity сообщения.
- **CHAT-P-FILE-002 [MUST/P2]** — Picker/paste/drop используют единую validation pipeline и одинаковые лимиты.
- **CHAT-P-FILE-003 [MUST/P2]** — Image получает inline preview; другие файлы получают file card с именем, типом, размером и status.
- **CHAT-P-FILE-004 [MUST/P2]** — Preview/download после reload проходит через authenticated Media delivery.
- **CHAT-P-FILE-005 [MUST/P2]** — PDF/DOCX/XLSX/CSV имеют валидированный extraction path; structure не должна без необходимости превращаться в один неразмеченный текст.
- **CHAT-P-FILE-006 [MUST/P2]** — Audio проходит через принятую ASR capability и сохраняет связь transcript ↔ source asset.
- **CHAT-P-FILE-007 [MUST/P2]** — Unsupported analysis показывает честное состояние «файл загружен, анализ этого формата пока недоступен».
- **CHAT-P-FILE-008 [MUST/P2]** — Extracted context сохраняет provenance как минимум до asset и применимой page/sheet/section/segment координаты.

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
- **CHAT-P-ADMIN-005 [MUST/P4]** — Effective availability вычисляется сервером с учётом account state, publication, entitlement, override, credential/provider health, modality и billing eligibility.

### 8.3. Daily allowance и Premium balance

В продукте есть два пользовательских ресурса, но это не означает заранее две физические таблицы ledger.

- **Daily allowance** — периодически выдаваемый/сбрасываемый ресурс по plan policy.
- **Premium balance** — сохраняемый пополняемый баланс для premium operations.

- **CHAT-P-SPEND-001 [MUST/P4]** — Server Spend Authority атомарно решает, разрешена ли операция и из какого ресурса она оплачивается.
- **CHAT-P-SPEND-002 [MUST/P4]** — Поддерживаются политики минимум: `FREE`, `DAILY_ONLY`, `PREMIUM_ONLY`, `DAILY_THEN_PREMIUM`, `BYOK`.
- **CHAT-P-SPEND-003 [MUST/P4]** — Для `DAILY_THEN_PREMIUM`: если daily недостаточно и потребуется premium, пользователь получает quote/confirmation, если у него нет явной opt-in policy на автодоплату.
- **CHAT-P-SPEND-004 [MUST/P4]** — `BYOK` означает, что provider charge идёт на ключ пользователя; отдельное списание IZO premium разрешено только если продуктовая цена явно это предусматривает и показана пользователю.
- **CHAT-P-SPEND-005 [MUST/P4]** — Paid platform execution использует reserve/settle/release/reconcile semantics и стабильный operation/request ID.
- **CHAT-P-SPEND-006 [MUST/P4]** — Provider input/output tokens/cost facts не называются пользовательскими credits.
- **CHAT-P-SPEND-007 [MUST/P4]** — UI показывает Daily allowance и Premium balance раздельно и не обещает нулевую стоимость при unknown outcome.

---

## 9. P5 — Release Acceptance

### 9.1. Security/product trust

- **CHAT-P-SEC-001 [MUST/P5]** — Account A не получает private Thread/Message/File/Image/Credential Account B без отдельного share/public contract.
- **CHAT-P-SEC-002 [MUST/P5]** — Контент загруженных документов, web/tool outputs и metadata считается untrusted data и не может повышать privileges, менять system/product policy или разрешать tool execution.
- **CHAT-P-SEC-003 [MUST/P5]** — Raw chain-of-thought/provider reasoning не является пользовательским output contract.
- **CHAT-P-SEC-004 [MUST/P5]** — Неподдержанный/опасный файл не исполняется автоматически.

### 9.2. Performance/accessibility

- **CHAT-P-NFR-001 [MUST/P5]** — Browser acceptance включает Chromium/Edge-compatible, Firefox и WebKit/Safari-compatible engine; mobile touch/keyboard сценарии обязательны.
- **CHAT-P-NFR-002 [MUST/P5]** — Длинный thread не требует полного reparsing/re-render всего разговора на каждый token.
- **CHAT-P-NFR-003 [MUST/P5]** — Все controls имеют accessible name, keyboard navigation и visible focus в двух темах.
- **CHAT-P-NFR-004 [MUST/P5]** — 320/390/768/1024/1440/1920 являются обязательными geometry checkpoints; QHD/UHD — smoke, а не замена browser-engine matrix.

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