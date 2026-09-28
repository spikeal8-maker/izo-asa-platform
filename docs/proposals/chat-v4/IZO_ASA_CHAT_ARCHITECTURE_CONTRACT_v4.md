# IZO ASA Chat — Architecture & Code/File Structure Contract v4

**Статус:** кандидат на стабильный архитектурный контракт.  
**Назначение:** определить data/domain ownership, import direction, структуру кода и файлов, контракты Context/Renderer/Providers/Tools/Files/Spend.  
**Интеграция в репозиторий:** положения должны быть распределены по существующим владельцам `ARCHITECTURE.md`, `AI_RUNTIME.md`, `ADMIN.md`, `UX.md`, `MAINTAINABILITY.md` и local README. Не создавать параллельный второй live `ARCHITECTURE` после принятия.

---

## 1. Архитектурные принципы

1. **Server authority first.** Browser не владеет identity, permissions, price, provider credentials, object keys, billing outcome или tool execution authority.
2. **One owner per fact.** Chat не создаёт второй Accounts/Credits/Jobs/Media/Catalog.
3. **Provider-neutral presentation.** Renderer/history/composer не знают provider-specific wire format.
4. **Conversation provider ≠ tool provider.** Текстовая LLM и image/ASR/document/video capability могут быть у разных runtime/providers.
5. **Normalize at boundaries.** Provider/file/tool outputs преобразуются в IZO contracts до попадания в UI.
6. **Split before growth.** Near-limit owner не расширяется новой ответственностью.
7. **No big-bang refactor.** Целевая структура достигается bounded migration packages с сохранением работающих contracts.

---

## 2. Domain ownership

| Domain | Владеет | Не владеет |
| --- | --- | --- |
| Accounts | identity, sessions, account state | Chat history, model catalog |
| Access/Admin | staff permissions, privileged commands | user balance implementation |
| Entitlements | plan/capability access, quotas/allowances | provider secret, ledger settlement |
| Credits | immutable premium financial ledger/reservations | plan eligibility, provider routing |
| Spend Authority | выбор FREE/DAILY/PREMIUM/BYOK и атомарная admission policy | provider call implementation |
| Catalog | product models/capabilities/prices/publication | raw chat history |
| Chat | thread/branch/messages/requests/context/tool proposals | binary files, ledger, provider global state |
| Media | private assets/storage/delivery/lifecycle | conversation semantics |
| File Processing | safe extraction/normalization/provenance | Media storage ownership |
| Artifacts (когда введён) | logical version chain generated results | binary storage |
| Jobs | durable long-running execution/lease/recovery | Chat rendering |
| Conversation Providers | transport к LLM, normalized stream/usage/errors | Credits/Media direct writes |
| Capability Runtimes | image/edit/ASR/doc generation/etc. | Chat UI state |

**ARCH-DOM-001 [MUST]** — новый feature не создаёт локальную копию чужого source of truth.  
**ARCH-DOM-002 [MUST]** — provider adapter возвращает нормализованный result/error/usage и не пишет напрямую в user/ledger/media tables.  
**ARCH-DOM-003 [MUST]** — Chat использует Media/Jobs/Catalog/Spend через публичные domain services/contracts.

---


## 3. Conversation data model

### 3.1. Сущности и cardinality

```text
Thread 1
 ├─ Branch 1..N
 │   ├─ parent_branch_id? + fork_from_turn_id?
 │   └─ ordered Turn 1..N
 │       ├─ UserMessage exactly 1
 │       │   └─ ordered MessageParts 0..N
 │       └─ AssistantAttempt 0..N
 │           ├─ ChatRequest exactly 1
 │           └─ ordered MessageParts 0..N
 └─ active_branch_id exactly 1 existing branch
```

`Turn` — логическая позиция разговора в branch. `UserMessage` immutable после admission. Root Branch не имеет parent/fork. Descendant Branch хранит `parent_branch_id` и `fork_from_turn_id`: это turn исходной ветви, пользовательскую реплику которого Edit заменяет новой immutable UserMessage в первом divergent turn.

`ChatRequest` — одна conversational execution identity для одного AssistantAttempt:

```text
ChatRequest
 ├─ request_id
 ├─ assistant_attempt_id
 ├─ material_fingerprint
 ├─ resolved execution snapshot
 ├─ state
 └─ provider/tool outcome references
```

Tool operations, предложенные внутри AssistantAttempt, получают собственные stable operation IDs/Jobs и не становятся дополнительными ChatRequest.

### 3.2. Правила операций

- **ARCH-MSG-001 [MUST]** — Edit user message создаёт descendant Branch с explicit `parent_branch_id + fork_from_turn_id` и новым immutable UserMessage; исходная branch/turn/message не изменяются. После успешного создания descendant Branch server transaction атомарно устанавливает `thread.active_branch_id` на неё. Новая Branch наследует selected-attempt mapping родителя только для prefix до fork point; edited turn начинает с `selected_attempt_id = NONE`, а parent answer после fork не переносится в selection.
- **ARCH-MSG-002 [MUST]** — Regenerate создаёт новый AssistantAttempt и ровно один новый ChatRequest для того же UserMessage в текущей active Branch; `active_branch_id` не меняется. Старый attempt/request сохраняется, а previous selected attempt остаётся selected до durable completion нового candidate.
- **ARCH-MSG-003 [MUST]** — Branch хранит persisted deterministic selected AssistantAttempt для каждого turn с альтернативами. Только `COMPLETED` attempt может стать ordinary context selection: durable completion Regenerate/safe retry переключает selection по transition table ниже; manual selector может атомарно выбрать другой `COMPLETED` attempt. `ERROR`/`UNKNOWN`/partial `STOPPED`/`INTERRUPTED` остаются history/evidence и не выбираются ordinary selector action.
- **ARCH-MSG-004 [MUST]** — UI и Context Engine используют persisted `active_branch_id` и selected-attempt mapping, а не «последнюю запись по времени». Manual Branch selection server-side атомарно устанавливает `thread.active_branch_id` на выбранную существующую Branch и использует её собственную persisted mapping без пересчёта по timestamp/DOM/stream order. Все branch/attempt selection transitions durably persisted и transactionally consistent; reload/restart восстанавливает тот же state.
- **ARCH-MSG-005 [MUST]** — Archive — состояние Thread, а не hard-delete audit/request/assets.
- **ARCH-MSG-006 [MUST]** — Retry не смешивается с Regenerate. Known pre-submit failure переигрывает тот же request identity/fingerprint и тот же AssistantAttempt; Branch/selection во время execution не меняются, а durable `COMPLETED` выбирает current candidate. Доказанный post-submit rejection/no-execution создаёт новый ChatRequest+AssistantAttempt с `retry_of_request_id` и следует Regenerate selection transitions. `UNKNOWN` никогда не меняет selection и запрещает новое execution до reconciliation.
- **ARCH-MSG-007 [MUST]** — P1 не имеет отдельной «Continue generating» execution semantics. Обычное продолжение — новый UserMessage в active Branch; отдельный assistant-continuation требует будущего versioned contract.

### 3.3. Normative branch/attempt transition semantics

Conversation Graph является единственным owner выбора Branch/AssistantAttempt. Context Engine не выбирает attempt самостоятельно: он получает persisted `active_branch_id` и selected-attempt mapping.

| Operation | Active branch | Selection while running | Completed | Error | Stopped / Interrupted | Unknown |
| --- | --- | --- | --- | --- | --- | --- |
| Edit | new descendant становится active сразу после успешного создания | edited turn = `NONE` | new edited-turn attempt selected | `NONE` | `NONE`; partial сохраняется только как history/evidence | `NONE` + block new execution until reconcile |
| Regenerate | unchanged | previous selected | new attempt selected | previous selected | previous selected; partial не выбирается | previous selected + block new execution until reconcile |
| Retry pre-submit | unchanged | previous/`NONE`; same request + same attempt | current candidate selected | previous/`NONE` | previous/`NONE` | previous/`NONE` + reconcile first |
| Retry safe post-submit | unchanged | previous/`NONE`; new request + new retry attempt | new retry attempt selected | previous/`NONE` | previous/`NONE` | previous/`NONE` + reconcile first |

Дополнительные нормативные правила:

- `COMPLETED` transition выполняется только после durable terminal persistence результата и selection update является server-owned, persisted и atomic.
- Для Edit descendant Branch наследует parent selected-attempt mapping только для prefix до `fork_from_turn_id`; состояние parent Branch и её post-fork answers не копируются в новый divergent suffix.
- Если Edit автоматически запускает attempt, `ERROR`/`STOPPED`/`INTERRUPTED` не выбирают parent answer; edited turn остаётся `NONE`.
- `UNKNOWN` сохраняет selection, указанный таблицей, блокирует новое execution для affected lifecycle и сначала reconciles исходный request. Reconciliation с доказанным `COMPLETED` применяет обычный Completed transition; no-execution/rejected/error применяет обычный failure transition и не выбирает uncertain/partial output.
- Manual attempt selection разрешён только среди `COMPLETED` attempts данного turn и atomically persists `selected_attempt_id`; timestamp, DOM order и last-streamed attempt не используются как authority.
- Manual Branch selection atomically persists `thread.active_branch_id` и активирует собственную persisted selected-attempt mapping выбранной Branch; другие Branch/attempts не удаляются.
- Любой automatic/manual branch или attempt transition, меняющий source range действующего summary, invalidates summary по существующему Context Engine contract; второй механизм summary не создаётся.

### 3.4. Message parts

Минимальный versioned registry:

- `markdown`
- `input_attachment_ref`
- `image_result_ref`
- `file_result_ref`
- `artifact_ref`
- `job_ref`
- `confirmation`
- `sources`
- `error_recovery`

Будущие `video_result`, `audio_result`, `model3d_result` добавляются versioned расширением.

**ARCH-PART-001 [MUST]** — unknown type/version fail-safe отображается как unsupported block, не raw provider JSON.  
**ARCH-PART-002 [MUST]** — Media/Job/File identity хранится как domain ID, не signed URL/object key/base64.  
**ARCH-PART-003 [MUST]** — один Markdown part может содержать много абзацев/таблиц/кода; DOM nodes не являются DB schema.

---

## 4. Context Engine

Context Engine — отдельный owner, а не побочная функция provider adapter.

Нормативный pipeline:

```text
persisted Thread
 → active Branch
 → selected AssistantAttempts
 → mandatory current-turn dependencies
 → model capability + context/output limits
 → deterministic budget calculator/version
 → eligible recent turn groups
 → optional versioned summary of older eligible prefix
 → normalized ConversationInput
 → ConversationProviderAdapter
```

Priority при budget pressure:

```text
1. System/Product policy
2. current UserMessage
3. current-turn required file/source/tool dependencies
4. selected eligible terminal AssistantAttempts + paired user turns, newest first
5. one valid summary of omitted older active-branch prefix
```

Ни current UserMessage, ни required current-turn dependency не truncates silently. Если mandatory set + reserved output не помещаются, admission fail до provider call.

- **ARCH-CTX-001 [MUST]** — persisted history и execution-context — разные сущности.
- **ARCH-CTX-002 [MUST]** — context builder использует capability/context/output limits resolved product model snapshot; calculator/tokenizer или conservative estimator + version/safety margin входят в execution snapshot.
- **ARCH-CTX-003 [MUST]** — failed/unknown/partial attempts не становятся ordinary assistant truth; в provider context попадают только выбранные eligible terminal attempts согласно versioned policy.
- **ARCH-CTX-004 [MUST]** — file excerpts/tool/source outputs имеют provenance и bounded contribution; raw previous-provider payload, secret и reasoning не переносятся между providers.
- **ARCH-CTX-005 [MUST]** — switching model пересчитывает budget/modalities/tools без изменения persisted history. Current-turn incompatible modality блокирует admission или требует compatible effective model; historical unsupported binary исключается, а normalized derived evidence используется только если поддержано и имеет provenance.
- **ARCH-CTX-006 [MUST]** — summary/reduction имеет `summary_id`, policy/version, active-branch source range и provenance. Summary invalidated при branch/edit divergence source range, selected-attempt change внутри range, изменении referenced source/tool/file result или несовместимом policy-version; invalid summary никогда не отправляется provider.
- **ARCH-CTX-007 [MUST]** — fixtures `128k→32k`, vision→text-only, tool-capable→tool-incapable и provider switch обязаны давать deterministic selected input/explicit denial при одинаковом persisted state и policy-version.

---

## 5. Response policy и presentation pipeline

```text
Product/System Response Policy
          ↓
Conversation Provider
          ↓
normalized Markdown + typed events/parts
          ↓
Durable Message
          ├─ Screen Renderer
          └─ Clipboard Serializer
```

**ARCH-RSP-001 [MUST]** — response formatting policy server-owned и provider-neutral.  
**ARCH-RSP-002 [MUST]** — raw chain-of-thought не входит в normalized message contract.  
**ARCH-RSP-003 [MUST]** — Renderer и Clipboard Serializer используют сохранённую нормализованную модель, а не копируют browser DOM.  
**ARCH-RSP-004 [MUST]** — rich clipboard sanitizes HTML и не включает toolbar/button/hidden UI.

---

## 6. Conversation Providers и Capability Runtimes

### 6.1. ConversationProviderAdapter

Отвечает только за conversational inference:

```text
verify_connection()
discover_conversation_models()
stream_conversation(input, execution_snapshot)
cancel(request_ref)          # если provider поддерживает
reconcile(request_ref)       # если provider поддерживает
normalize_usage()
normalize_error()
```

DeepSeek/OpenRouter — реализации этого интерфейса. Future provider добавляется здесь.

### 6.2. Capability Runtime

Image generation/edit, ASR, file creation, video и другие tools не должны быть методами ConversationProviderAdapter.

```text
CapabilityDefinition
 ├─ kind: image.generate | image.edit | asr | document.generate | ...
 ├─ input contract
 ├─ output contract
 ├─ billing/confirmation class
 └─ runtime/provider binding
```

**ARCH-PROV-001 [MUST]** — `generateImage()`/`generatePdf()` не являются обязательными методами Chat LLM adapter.  
**ARCH-PROV-002 [MUST]** — Conversation model MAY нативно предлагать tool calls, но server Tool Orchestrator валидирует их и выбирает capability runtime.  
**ARCH-PROV-003 [MUST]** — model/provider discovery создаёт candidates/facts; product publication остаётся Catalog/Admin authority.

---

## 7. Tool Orchestrator

Server-only pipeline:

```text
User intent / model proposal
 → normalize proposal
 → validate permissions + capability + inputs
 → quote / confirmation if needed
 → stable operation ID
 → shared Job or bounded synchronous executor
 → capability runtime/provider
 → Media/File/Artifact output
 → typed result block in Chat
```

- **ARCH-TOOL-001 [MUST]** — Browser не вызывает provider tool endpoint напрямую.
- **ARCH-TOOL-002 [MUST]** — Paid/опасная/неоднозначная операция требует server policy; модель не может сама разрешить расход.
- **ARCH-TOOL-003 [MUST]** — Long-running media tools используют shared Jobs, а не Chat-private queue.
- **ARCH-TOOL-004 [MUST]** — terminal tool result является domain asset/job/file и может использоваться Gallery/Studio без копирования данных.
- **ARCH-TOOL-005 [MUST]** — unknown external outcome блокирует blind retry до reconciliation policy.

---


## 8. File ingestion и processing

### 8.1. Storage

Media остаётся единственным binary storage owner. Filename, extension и browser-provided MIME — presentation metadata, не trust signal.

### 8.2. Trusted type selection

Pipeline:

```text
owned Media asset bytes
 → bounded signature/structure detection
 → trusted actual format
 → allowlisted parser
 → bounded extraction
 → normalized representation + provenance
```

Declared/actual mismatch либо fail-closed отклоняется, либо нормализуется только к безопасному detected type по server policy. Browser не выбирает parser. Parser/extractor egress, external relationships/resources и active content default-deny.

### 8.3. Processing

Shared File Processing layer выполняет bounded extraction:

- PDF: pages/text + optional page images;
- DOCX: paragraphs/tables/relationships без исполнения active content;
- XLSX/CSV/TSV: workbook/sheet/range/formula facts;
- TXT/MD/source: bounded text;
- HTML/XML/YAML/JSON: sanitized/parsed structure без active fetch/execute;
- audio: ASR capability + source segments;
- video: отдельный deferred capability; P2 core не требует deep analysis.

**ARCH-FILE-001 [MUST]** — parsers получают byte stream/asset through Media service, а не arbitrary local path/object key from browser.  
**ARCH-FILE-002 [MUST]** — extracted representation содержит asset + page/sheet/range/section/segment provenance где применимо.  
**ARCH-FILE-003 [MUST]** — parsing bounded по bytes/pages/cells/nesting/decompression/resources/time; decompression/archive bombs fail closed.  
**ARCH-FILE-004 [MUST]** — macros/scripts, XML entities, SVG/HTML active content, Office external relationships и parser-driven external network fetch не исполняются; egress default-deny.  
**ARCH-FILE-005 [MUST]** — PDF/Office/HTML/SVG/XML/archive/spreadsheet inputs рассматриваются как untrusted data; formula-like content не превращается в executable spreadsheet output без explicit generation/edit policy.  
**ARCH-FILE-006 [MUST]** — parser выбирается только по server-owned trusted actual format; extension/client MIME spoof не может переключить parser или ослабить limits.

## 9. Generated Files и Artifact Runtime

### 9.1. Computation/File Runtime

Создание/преобразование документов выполняется в изолированном runtime с allowlisted libraries.

```text
Normalized tool command
 → ephemeral workspace
 → approved generator/processor
 → validation
 → Media asset
 → optional Artifact version
 → Chat FileResult
```

- **ARCH-ART-001 [MUST]** — sandbox не имеет Docker socket/host filesystem/private network/secrets по умолчанию.
- **ARCH-ART-002 [MUST]** — network egress default-deny; разрешается только конкретному tool/provider по policy.
- **ARCH-ART-003 [MUST]** — generated output валидируется до публикации: magic/type, size, parser-openability и ожидаемая structure.
- **ARCH-ART-004 [MUST]** — GeneratedFile может существовать без отдельного rich editor.
- **ARCH-ART-005 [MUST]** — Artifact, если введён, хранит logical identity/version/provenance и ссылается на Media versions, не дублирует binary storage.

---


## 10. Catalog: models vs capabilities

Catalog различает как минимум:

1. **ConversationProductModel** — text/vision/file-capable conversational model.
2. **ToolCapability** — image.generate, image.edit, asr, document.generate, video.generate и т. п.
3. **RuntimeBinding** — конкретный provider/runtime для capability.

**ARCH-CAT-001 [MUST]** — FLUX/image model не публикуется как text conversation model только потому, что это «AI model».  
**ARCH-CAT-002 [MUST]** — provider raw cost и user-visible IZO price — разные поля/owners.  
**ARCH-CAT-003 [MUST]** — retire сохраняет historical references.  
**ARCH-CAT-004 [MUST]** — discovery создаёт candidate/facts, а effective model/capability projection вычисляется одной server-side authority после Admin publication и access checks.

### 10.1. Effective model hard-deny envelope

Порядок admission:

```text
candidate/provider facts
 → product model exists
 → not retired
 → enabled
 → published
 → account active
 → provider/runtime available
 → required credential available
 → capability/modality compatible
 → billing eligible
 → plan entitlement
 → optional account override within global envelope
 → EFFECTIVE
```

Retired/disabled/unpublished, restricted account, unavailable provider/credential, incompatible capability/modality и billing-ineligible — hard deny. Plan/user override не может re-enable hard-denied model. Override может только сузить доступ либо разрешить вариант, который уже находится внутри global published+enabled envelope и разрешён server policy. Frontend только отображает effective projection.

**ARCH-CAT-005 [MUST]** — все Chat admissions, model selector/API и tool routing используют одну effective authority/revision; browser-side union remote discovery + local models не является access decision.  
**ARCH-CAT-006 [MUST]** — изменение Admin publication/disable запрещает новые admissions после effective revision change, но не переписывает immutable snapshot уже принятого request/job.

---

## 11. Spend Authority: Daily + Premium + BYOK

Продукт требует Daily allowance и Premium balance, но физическая persistence-модель выбирается ADR после анализа существующих Credits/Entitlements.

Логический result:

```text
SpendDecision authorize(account, product_operation, quote_context)
 → allowed / denied
 → FundingPlan {
      sources[{resource, authorized_amount, reservation_or_claim_id?}],
      settlement_rule,
      confirmation_required,
      provider_payer,
      platform_fee
   }
```

Policy semantics:

- `FREE`: user resources не claim/reserve; product price zero и нет billable provider/runtime charge для этой operation. Если внешний расход несёт платформа, используется `PLATFORM_FUNDED`.
- `PLATFORM_FUNDED`: platform является provider payer; user Daily/Premium не списываются.
- `DAILY_ONLY`: full price atomically claims/reserves Daily or deny.
- `PREMIUM_ONLY`: full price резервируется через existing Premium Credits primitives.
- `DAILY_THEN_PREMIUM/DAILY_FIRST`: Daily first, Premium = exact shortfall; daily=3, price=5 → Daily 3 + Premium 2.
- `MIXED`: explicit versioned split from product policy/quote; all sources authorize atomically.
- `BYOK`: provider payer=user; no hidden Daily/Premium debit. Optional platform service fee is separate line item with separate FundingPlan/confirmation.

Lifecycle каждого FundingPlan: `authorize → claim/reserve → execute → settle/release`; unknown external outcome удерживает provisional state и идёт в `reconcile` без blind retry. Resource-specific persistence может различаться, но atomic admission не допускает partial funding side effects.

**ARCH-SPEND-001 [MUST]** — Chat UI/Provider/model не решают, какой resource списать и не формируют FundingPlan.  
**ARCH-SPEND-002 [MUST]** — existing immutable Credits ledger/reserve/settle/release не переписывается в два wallet «по предположению»; Daily persistence и cross-resource atomicity требуют ADR/migration/reconciliation tests.  
**ARCH-SPEND-003 [MUST]** — Daily→Premium semantics ровно daily-first + exact Premium shortfall; Premium part требует confirmation без explicit opt-in.  
**ARCH-SPEND-004 [MUST]** — BYOK provider cost и platform fee — разные accounting lines; provider cost пользователя не превращается автоматически в IZO Premium debit.  
**ARCH-SPEND-005 [MUST]** — unknown outcome сохраняет funding reservations/claims в reconcile state до доказанного settlement/release policy; unknown не считается zero-cost.

## 12. Security trust hierarchy

```text
System/Product policy + server authorization
              >
Authenticated user intent
              >
Untrusted model/file/web/tool content
```

Untrusted content может информировать модель, но не может:

- выдавать себе permission;
- менять billing policy;
- извлекать secrets;
- разрешать network/host access;
- самостоятельно подтверждать tool execution;
- подменять owner IDs/object keys.

### Prompt injection

**ARCH-SEC-001 [MUST]** — attachment/web/tool text всегда маркируется как untrusted context.  
**ARCH-SEC-002 [MUST]** — tool command после model proposal повторно валидируется сервером по allowlist/schema/ownership/price.  
**ARCH-SEC-003 [MUST]** — секреты не добавляются в model context без отдельной минимальной server-side необходимости.  
**ARCH-SEC-004 [MUST]** — logs/traces используют IDs/phase/size/error; raw user docs/prompts не логируются целиком по умолчанию.  
**ARCH-SEC-005 [MUST]** — zip/decompression bombs, malicious XML entities, Office external links/macros, SVG/script, HTML active content и spreadsheet formula injection имеют отдельные parser/sanitization tests.

---

## 13. Target frontend file architecture

Это **целевая карта ответственности**, а не требование одномоментно переместить весь текущий `shell/chat`.

```text
apps/web/src/features/chat/
  README.md
  ChatWorkspace.tsx              # composition only
  api/
    chatApi.ts
    chatTypes.ts
  state/
    useChatSession.ts
    useChatStream.ts
    useChatRecovery.ts
  thread/
    ThreadList.tsx
    ThreadDrawer.tsx
    ThreadActions.tsx
  messages/
    MessageStream.tsx
    MessageActions.tsx
    ScrollAnchor.ts
  renderer/
    MarkdownMessage.tsx
    CodeBlock.tsx
    TableBlock.tsx
    MathBlock.tsx
    SafeLink.tsx
    clipboardSerializer.ts
  composer/
    Composer.tsx
    ModelPicker.tsx
    AttachmentTray.tsx
    VoiceControl.tsx
  attachments/
    attachmentValidation.ts
    AttachmentPreview.tsx
    FileCard.tsx
  blocks/
    ImageResultBlock.tsx
    FileResultBlock.tsx
    JobBlock.tsx
    ConfirmationBlock.tsx
    SourcesBlock.tsx
    ErrorRecoveryBlock.tsx
```

`src/shell/ChatPage.tsx` MAY оставаться route/shell composition и импортировать `features/chat`, но не должен владеть runtime/business logic.

### Frontend file rules

- **ARCH-FE-001 [MUST]** — Network + complex state + presentation не объединяются в один growing component.
- **ARCH-FE-002 [MUST]** — Renderer modules не импортируют Accounts/Admin/Credits/provider internals.
- **ARCH-FE-003 [MUST]** — Sibling feature internals не импортируются напрямую; reusable primitives/data clients переходят в `shared/` только после второго реального consumer.
- **ARCH-FE-004 [MUST]** — CSS owner следует component/domain owner; giant shared chat stylesheet не должен расти бесконечно.
- **ARCH-FE-005 [MUST]** — тяжелые math/highlight/viewer/editor dependencies lazy-load там, где применимо.

---

## 14. Target backend file architecture

Цель — разделить текущие near-limit `catalog.py`, `conversations.py`, `provider.py`, `execution.py`, `service.py` до добавления новых крупных обязанностей.

Возможная последовательная структура:

```text
apps/api/izo/chat/
  README.md
  routes_threads.py
  routes_requests.py
  routes_credentials.py
  schemas_public.py

  thread_service.py
  branch_service.py
  message_repository.py
  request_service.py
  request_state.py

  context_builder.py
  response_policy.py
  stream_events.py

  provider_registry.py
  provider_deepseek.py
  provider_openrouter.py
  provider_errors.py

  attachment_refs.py
  vision_context.py
  tool_orchestration.py          # только Chat-facing proposals/results
```

Shared cross-domain owners не помещаются внутрь Chat:

```text
izo/media/                 # storage/delivery
izo/jobs/                  # long execution
izo/catalog/               # product models/capabilities/prices
izo/credits/               # premium immutable ledger
izo/entitlements/          # plan/access/allowance policy
<shared file processing>   # вводится отдельным bounded package
<artifact/runtime owner>   # вводится только при реальной потребности
```

### Backend file rules

- **ARCH-BE-001 [MUST]** — `routes_*` — transport/auth/input mapping, не бизнес-процесс.
- **ARCH-BE-002 [MUST]** — `service.py` не становится omnibus Chat owner; новая ответственность получает owner module.
- **ARCH-BE-003 [MUST]** — provider adapters не открывают прямые transactions Credits/Media/Accounts.
- **ARCH-BE-004 [MUST]** — Context Engine, request state и branch semantics имеют собственные tests и не прячутся в provider code.
- **ARCH-BE-005 [MUST]** — migrations аддитивны и не используются как место бизнес-логики.

---

## 15. Import direction

### Web

```text
shell/router
   ↓
features/chat composition
   ↓
chat owners/components/hooks
   ↓
shared UI/API primitives
```

Запрещено: `chat renderer → admin`, `chat composer → gallery internals`, `feature A → feature B private module`.

### API

```text
HTTP routes
  ↓
Chat application services
  ↓
Chat domain/repositories/context
  ↓
public domain services/contracts
  ↓
provider/capability adapters
```

Provider не идёт «вверх» и не вызывает route/UI code.

---

## 16. Testing architecture

Каждый owner имеет ближайший тест.

- renderer → dedicated browser fixture suite;
- clipboard serializer → unit + browser clipboard smoke;
- context builder → deterministic context cases;
- branches/attempts → PostgreSQL integration;
- provider adapters → fake transport + contract tests;
- file parsers → malicious/oversize fixtures;
- tool orchestrator → idempotency/confirmation/job handoff;
- generated files → structural open/parse validation;
- spend → duplicate/unknown/refund/mixed resource tests;
- security boundaries → cross-account/prompt-injection/sandbox negative tests.

**ARCH-TEST-001 [MUST]** — geometry tests не заменяют semantic renderer tests.  
**ARCH-TEST-002 [MUST]** — live paid smoke отдельно от deterministic CI; отсутствие owner-approved live spend = `NOT_RUN`, не `PASS`.

---

## 17. Migration from current code

1. Не делать массовый rename/move только ради красивого дерева.
2. Первый новый feature, который требует расширить near-limit owner, сначала выполняет bounded split с characterization tests.
3. Новые owners получают local README/context route только если являются самостоятельным domain/feature согласно `DOCS_SYSTEM.md`.
4. Старые public endpoints/contracts сохраняются либо мигрируют versioned способом.
5. Любое перемещение обязанностей заканчивается удалением старой дублирующей live path после proof/evidence; временная двойная реализация имеет expiry package.

**ARCH-MIG-001 [MUST]** — target tree — направление, не разрешение на big-bang refactor.  
**ARCH-MIG-002 [MUST]** — split/relocation не меняет product behavior без отдельного requirement.  
**ARCH-MIG-003 [MUST]** — после migration package не остаётся два активных owner одного и того же факта.