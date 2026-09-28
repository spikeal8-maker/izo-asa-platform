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

### 3.1. Сущности

```text
Thread
 ├─ Branch
 │   └─ ordered Turns
 │       ├─ UserMessage
 │       │   └─ ordered MessageParts
 │       └─ AssistantAttempt[1..N]
 │           └─ ordered MessageParts
 └─ active_branch_id

ChatRequest
 ├─ request_id
 ├─ material_fingerprint
 ├─ resolved execution snapshot
 ├─ state
 └─ provider/tool outcome references
```

### 3.2. Правила ветвления

- **ARCH-MSG-001 [MUST]** — Edit user message создаёт новую `Branch` от parent point; исходная branch immutable для истории.
- **ARCH-MSG-002 [MUST]** — Regenerate создаёт новую `AssistantAttempt` для того же UserMessage; user message не дублируется.
- **ARCH-MSG-003 [MUST]** — Branch хранит выбор активной attempt для каждого turn, если попыток несколько.
- **ARCH-MSG-004 [MUST]** — UI и Context Engine используют `active_branch_id`, а не эвристику «последняя запись по времени».
- **ARCH-MSG-005 [MUST]** — Archive — состояние thread, а не hard-delete audit/request/assets.

### 3.3. Message parts

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

Pipeline:

```text
Thread history
 → active branch
 → selected assistant attempts
 → eligible terminal messages/tool results
 → source/file evidence selection
 → model-specific budget
 → optional reduction/summarization
 → normalized ConversationInput
 → ConversationProviderAdapter
```

- **ARCH-CTX-001 [MUST]** — история и execution-context — разные сущности.
- **ARCH-CTX-002 [MUST]** — context builder знает capability/context limit выбранной product model из resolved snapshot.
- **ARCH-CTX-003 [MUST]** — failed/unknown/partial attempts не становятся ordinary assistant truth без явной policy.
- **ARCH-CTX-004 [MUST]** — file excerpts/tool outputs имеют provenance и bounded contribution.
- **ARCH-CTX-005 [MUST]** — switching model пересчитывает budget и modalities, не меняя сохранённую историю.
- **ARCH-CTX-006 [SHOULD]** — summarization имеет source range/provenance и version, чтобы её можно было заменить без порчи исходной истории.

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

Media остаётся единственным binary storage owner.

### 8.2. Processing

Shared File Processing layer выполняет bounded extraction:

- PDF: pages/text + optional page images;
- DOCX: paragraphs/tables/relationships без исполнения active content;
- XLSX/CSV: workbook/sheet/range/formula facts;
- HTML/XML/YAML/JSON/code: data/text sanitization;
- audio: ASR capability;
- future video: metadata/frames/audio through dedicated capability.

**ARCH-FILE-001 [MUST]** — parsers получают byte stream/asset through Media service, а не arbitrary local path/object key from browser.  
**ARCH-FILE-002 [MUST]** — extracted representation содержит provenance.  
**ARCH-FILE-003 [MUST]** — parsing bounded по bytes/pages/cells/nesting/decompression/resources.  
**ARCH-FILE-004 [MUST]** — macros/scripts/external relationships не исполняются.  
**ARCH-FILE-005 [MUST]** — PDF/Office/HTML/SVG и архивные containers рассматриваются как untrusted inputs.

---

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

Catalog должен различать как минимум:

1. **ConversationProductModel** — text/vision/file-capable conversational model.
2. **ToolCapability** — image.generate, image.edit, asr, document.generate, video.generate и т. п.
3. **RuntimeBinding** — конкретный provider/runtime для capability.

**ARCH-CAT-001 [MUST]** — FLUX/image model не публикуется как text conversation model только потому, что это «AI model».  
**ARCH-CAT-002 [MUST]** — provider raw cost и user-visible IZO price — разные поля/owners.  
**ARCH-CAT-003 [MUST]** — retire сохраняет historical references.  
**ARCH-CAT-004 [MUST]** — effective model/capability projection вычисляется сервером.

---

## 11. Spend Authority: Daily + Premium + BYOK

Продукт требует два пользовательских ресурса, но физическая persistence-модель выбирается отдельным ADR после анализа Credits/Entitlements.

Логическая функция:

```text
SpendDecision authorize(account, product_operation, quote_context)
 → allowed / denied
 → funding_plan
 → reservations/allowance claims
 → confirmation requirement
```

Возможные реализации:

- bucketed ledger;
- daily entitlement allowance + premium Credits ledger;
- другая единая authority, сохраняющая атомарность.

**ARCH-SPEND-001 [MUST]** — Chat UI/Provider не решают, какой resource списать.  
**ARCH-SPEND-002 [MUST]** — existing immutable Credits ledger не переписывается в два wallet «по предположению»; изменение финансовой схемы требует ADR/migration/reconciliation tests.  
**ARCH-SPEND-003 [MUST]** — mixed daily→premium semantics фиксируются product policy и тестируются.  
**ARCH-SPEND-004 [MUST]** — BYOK provider cost не маскируется platform charge и наоборот.

---

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