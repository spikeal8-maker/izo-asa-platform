# IZO ASA Chat v4 — Adoption & Traceability Plan

**Статус:** APPROVED SOURCE SNAPSHOT · ADOPTED INTO CANONICAL OWNERS · NON-CANONICAL FOR FUTURE IMPLEMENTATION.
**Назначение:** transition/provenance evidence для Product/Architecture/Maintenance v4 и platform Source-First/Delivery adoption.
**Важно:** этот файл не является постоянным `ROADMAP/NOW/MASTER_PLAN`; live authority находится в Issue #222/PRODUCT, ARCHITECTURE, AI_RUNTIME, ADMIN, UX, MAINTAINABILITY, DOCS_SYSTEM/DEVELOPMENT и current state owners.

---

## 1. Snapshot, использованный для подготовки

На момент проверки:

- repository: `spikeal8-maker/izo-asa-platform`;
- active package: `CHAT-VISION-001`;
- branch: `codex/chat-vision-001`;
- PR: `#236`, OPEN/Draft;
- source HEAD: `2a2995ee47c8c369b512c1328f02d3eb662775a3`;
- required workflows для этого SHA были success;
- independent GitHub review для #236 отсутствовал на момент проверки;
- `main` всё ещё не является текущей рабочей продуктовой lineage; разработка идёт через verified stacked checkpoints.

Snapshot не переносится в stable Product/Architecture/Maintenance specs.

---

## 2. Что меняется относительно v3

| Дефект v3 | Исправление v4 |
| --- | --- |
| Один гигантский `CHAT_CORE_V1_ACCEPTED` | P1–P5 последовательные product gates |
| Product/architecture/current смешаны | Разделены Product / Architecture / Maintenance / Adoption |
| Все требования помечены MUST | Реальные MUST/SHOULD/MAY/DEFERRED |
| Context Engine недоописан | Отдельный owner и branch/attempt semantics |
| Renderer без model response policy | Добавлен Response Formatting Contract |
| ProviderAdapter смешивал chat и tools | ConversationProviderAdapter отделён от Capability Runtime |
| Model и tool catalog смешаны | ConversationProductModel vs ToolCapability |
| Generated files и Artifacts смешаны | Generated File обязателен; rich editor deferred |
| Sandbox описан слишком общо | Computation/File Runtime + validation + default-deny egress |
| Daily/Premium преждевременно выбраны как 2 buckets | Логический Spend Authority; persistence — ADR |
| Prompt injection почти не описан | Untrusted data hierarchy + server revalidation |
| Current HEAD был внутри stable spec | Current facts только здесь/PLAN/CURRENT |
| Нет обязательной структурной чистки | 3-package Chat audit + 5-package repo audit + 30-day backstop |

---

## 3. Куда переносить v4 в существующую документацию

### Canonical product

- **Issue #222** — заменить body на сокращённую каноническую версию `Chat Product Specification v4` с P1–P5 и acceptance.
- **Issue #43** — сохранить как MIG/overall Chat owner, но убрать противоречия с #222 v4.
- **#87/#88/#139/#140/#141** — оставить functional owners, обновить только те части, где v4 меняет branch/context/renderer/composer contract.

### Stable repository docs

| Документ | Из v4 добавить |
| --- | --- |
| `docs/PRODUCT.md` | Chat Product V1 summary, P1–P5, Daily/Premium/BYOK behavior |
| `docs/UX.md` | renderer/actions/composer/mobile/browser matrix |
| `docs/ARCHITECTURE.md` | branch/attempt, Context Engine, domain ownership, file/tool/artifact boundaries |
| `docs/AI_RUNTIME.md` | ConversationProviderAdapter vs Capability Runtime, stream normalization, reconcile |
| `docs/ADMIN.md` | discovery→product model→publish/access/pricing workflow |
| `docs/MAINTAINABILITY.md` | Chat 3-package audit, 30-day backstop, temporary-code expiry, garbage policy; source-first/donor classification и NEW_DECISION gate |
| `docs/DOCS_SYSTEM.md` | GitHub handoff/provenance: source references и восстановимый SOURCE_AUDIT без chat-only reasoning |
| `docs/PRODUCT.md` | дополнительно platform delivery order и статусы VISIBLE/FUNCTIONAL/ACCEPTED для крупных поверхностей |
| `docs/ADMIN.md` | дополнительно Admin A1/A2/A3: Chat control plane → modality/publication control → extended operations |
| local Chat README | краткие live owners/invariants/tests после фактической структуры |
| `BLOCK_MAP/CONTEXT_MAP` | новые owners только по мере появления реального кода |

### Mutable state

- `PLAN.json`/`CURRENT.md` меняются только через действующий state-transition workflow после принятия exact-head checkpoint.
- CI evidence остаётся в `CHECKPOINTS.json`/reviews.

---

## 4. Рекомендуемая последовательность convergence

### E0 — Spec adoption only

Цель: принять v4 семантически, не менять product code.

1. owner подтверждает Product v4 и platform-level `IZO_ASA_PLATFORM_SOURCE_DELIVERY_CONTRACT_v1.md`;
2. обновляется #222;
3. синхронизируются противоречащие owner issues;
4. `PRODUCT.md` получает platform delivery map `VISIBLE / FUNCTIONAL / ACCEPTED` и Chat-first sequencing;
5. `MAINTAINABILITY.md` получает source hierarchy, donor classification и `NEW_DECISION_REQUIRED` gate;
6. `DOCS_SYSTEM.md` получает provenance/SOURCE_AUDIT handoff contract;
7. `ADMIN.md` получает Admin A1/A2/A3 delivery boundaries;
8. stable docs получают только принадлежащие им факты без дублирующего live owner;
9. docs checks проходят;
10. current execution lineage не переписывается автоматически.

### E1 — Current active package reconciliation

`CHAT-VISION-001` сначала получает обычный exact-head review/waiver и фиксированный статус. Не добавлять в него v4 renderer/files/admin/credits scope.

После freeze создаётся следующий bounded package через repository state workflow.

### E2 — P1 Conversation Experience convergence

Приоритет после текущего vision checkpoint:

1. split near-limit Chat owners, затрагиваемых P1;
2. branch/regenerate/edit semantics;
3. Context Engine;
4. Response Formatting Contract;
5. full renderer + Clipboard Serializer;
6. history pagination/rename/archive/restore/recovery;
7. dedicated semantic browser acceptance.

**STOP:** P1 acceptance before new large capability family.

### E3 — P2 Multimodal Input

- file ingestion contract;
- PDF/DOCX/XLSX/CSV extraction/provenance;
- existing image vision convergence;
- audio/ASR input;
- truthful unsupported states;
- prompt-injection/parser security tests.

### E4 — P3 Creation & Tools

- Tool Orchestrator convergence;
- Computation/File Runtime;
- generated file outputs;
- version chain;
- image generation/edit.

### E5 — P4 Product Control

- Conversation model vs Tool capability catalog;
- Admin workflow/effective availability;
- Spend Authority ADR;
- Daily/Premium/BYOK behavior;
- migrations and high-risk review.

### E6 — P5 hardening/release

- security boundary audit;
- long-thread/performance;
- browser engines/a11y;
- clean restart/package;
- live smokes with owner-approved spend;
- `CHAT_PRODUCT_V1_ACCEPTED` and отдельно `CHAT_PORTABLE_RELEASE_ACCEPTED`.

---

## 5. MUST-level requirement traceability

Каждый acceptance-blocking MUST ниже имеет разрешимую цепочку `Requirement → canonical authority → owner → product gate → test/evidence class → status`. Группировка допустима только для IDs с одинаковыми authority/owner/gate/evidence/status; разные gate разделены.

Status `ADOPTED` означает: requirement перенесён в указанный canonical authority в E0. Это **не** означает `IMPLEMENTED`, `TESTED` или product-gate `PASS`; такие статусы появляются только с привязанным runtime/test/evidence соответствующего bounded implementation package.

| Requirement IDs | Canonical authority after adoption | Owner | Product gate | Required test/evidence class | Status |
| --- | --- | --- | --- | --- | --- |
| `ARCH-ART-001`, `ARCH-ART-002`, `ARCH-ART-003`, `ARCH-ART-004`, `ARCH-ART-005` | docs/ARCHITECTURE.md | Computation/File Runtime | P3 | sandbox negative + generated-file validation | ADOPTED |
| `ARCH-BE-001`, `ARCH-BE-002`, `ARCH-BE-003`, `ARCH-BE-004`, `ARCH-BE-005` | docs/ARCHITECTURE.md + local Chat README | Chat backend ownership | owning P1–P4 gate | import/owner guard + service/repository tests | ADOPTED |
| `ARCH-CAT-001`, `ARCH-CAT-002`, `ARCH-CAT-003`, `ARCH-CAT-004`, `ARCH-CAT-005`, `ARCH-CAT-006` | docs/ADMIN.md + docs/AI_RUNTIME.md | Catalog / Effective Model Authority | P4 | discovery/publication/access/audit tests | ADOPTED |
| `ARCH-CTX-001`, `ARCH-CTX-002`, `ARCH-CTX-003`, `ARCH-CTX-004`, `ARCH-CTX-005`, `ARCH-CTX-006`, `ARCH-CTX-007` | docs/ARCHITECTURE.md + docs/AI_RUNTIME.md | Context Engine | P1 | deterministic context fixtures | ADOPTED |
| `ARCH-DOM-001`, `ARCH-DOM-002`, `ARCH-DOM-003` | docs/ARCHITECTURE.md | Domain ownership | owning P1–P4 gate + P5 final | architecture/import + cross-domain integration | ADOPTED |
| `ARCH-FE-001`, `ARCH-FE-002`, `ARCH-FE-003`, `ARCH-FE-004`, `ARCH-FE-005` | docs/ARCHITECTURE.md + local Chat README | Chat frontend ownership | owning P1–P4 gate | import/owner guard + nearest component/browser tests | ADOPTED |
| `ARCH-FILE-001`, `ARCH-FILE-002`, `ARCH-FILE-003`, `ARCH-FILE-004`, `ARCH-FILE-005`, `ARCH-FILE-006` | docs/ARCHITECTURE.md | File Processing | P2 | malicious/oversize/mime-spoof parser tests | ADOPTED |
| `ARCH-MIG-001`, `ARCH-MIG-002`, `ARCH-MIG-003` | docs/ARCHITECTURE.md + docs/MAINTAINABILITY.md | Bounded migration | each migration package + P5 final | characterization + diff/owner cleanup evidence | ADOPTED |
| `ARCH-MSG-001`, `ARCH-MSG-002`, `ARCH-MSG-003`, `ARCH-MSG-004`, `ARCH-MSG-005`, `ARCH-MSG-006`, `ARCH-MSG-007` | docs/ARCHITECTURE.md | Conversation Graph | P1 | PostgreSQL branch/attempt/request integration | ADOPTED |
| `ARCH-PART-001`, `ARCH-PART-002`, `ARCH-PART-003` | docs/ARCHITECTURE.md | Message Part registry | P1/P3 | versioned schema + unsupported-part tests | ADOPTED |
| `ARCH-PROV-001`, `ARCH-PROV-002`, `ARCH-PROV-003` | docs/AI_RUNTIME.md | Conversation Provider adapters | P4 | fake transport/provider contract tests | ADOPTED |
| `ARCH-RSP-001`, `ARCH-RSP-002`, `ARCH-RSP-003`, `ARCH-RSP-004` | docs/AI_RUNTIME.md + docs/UX.md | Response pipeline | P1 | response policy + serializer tests | ADOPTED |
| `ARCH-SEC-001`, `ARCH-SEC-002`, `ARCH-SEC-003`, `ARCH-SEC-004`, `ARCH-SEC-005` | docs/ARCHITECTURE.md | Security trust boundary | P2/P3/P5 | prompt-injection/sandbox/cross-account negative tests | ADOPTED |
| `ARCH-SPEND-001`, `ARCH-SPEND-002`, `ARCH-SPEND-003`, `ARCH-SPEND-004`, `ARCH-SPEND-005` | docs/ARCHITECTURE.md | Spend Authority | P4 | financial race/reconcile/mixed-source tests | ADOPTED |
| `ARCH-TEST-001`, `ARCH-TEST-002` | docs/ARCHITECTURE.md | Test architecture | each owning P1–P5 gate | required owner suites + exact-head CI/live evidence split | ADOPTED |
| `ARCH-TOOL-001`, `ARCH-TOOL-002`, `ARCH-TOOL-003`, `ARCH-TOOL-004`, `ARCH-TOOL-005` | docs/ARCHITECTURE.md + docs/AI_RUNTIME.md | Tool Orchestrator | P3/P4 | idempotency/confirmation/job handoff | ADOPTED |
| `CHAT-P-ACT-001`, `CHAT-P-ACT-002`, `CHAT-P-ACT-003`, `CHAT-P-ACT-004`, `CHAT-P-ACT-005` | docs/UX.md | Message actions / Clipboard | P1 | serializer unit + real browser clipboard | ADOPTED |
| `CHAT-P-ADMIN-001`, `CHAT-P-ADMIN-002`, `CHAT-P-ADMIN-003`, `CHAT-P-ADMIN-004`, `CHAT-P-ADMIN-005` | docs/ADMIN.md | Admin model authority | P4 | permission/CAS/audit/effective projection | ADOPTED |
| `CHAT-P-ART-001` | Issue #222 + docs/ARCHITECTURE.md | Artifact logical versions | P3 | artifact/version integration | ADOPTED |
| `CHAT-P-COMP-001`, `CHAT-P-COMP-002`, `CHAT-P-COMP-005`, `CHAT-P-COMP-006` | docs/UX.md + docs/AI_RUNTIME.md | Composer / model selection | P1 | browser E2E + request snapshot/admission | ADOPTED |
| `CHAT-P-COMP-003`, `CHAT-P-COMP-004` | docs/UX.md + docs/AI_RUNTIME.md | Composer / model selection | P2 | browser E2E + request snapshot/admission | ADOPTED |
| `CHAT-P-CTX-001`, `CHAT-P-CTX-002`, `CHAT-P-CTX-003`, `CHAT-P-CTX-004`, `CHAT-P-CTX-006`, `CHAT-P-CTX-007`, `CHAT-P-CTX-008`, `CHAT-P-CTX-009` | docs/ARCHITECTURE.md + docs/AI_RUNTIME.md | Context Engine | P1 | deterministic context/model-switch fixtures | ADOPTED |
| `CHAT-P-FILE-001`, `CHAT-P-FILE-002`, `CHAT-P-FILE-003`, `CHAT-P-FILE-004`, `CHAT-P-FILE-005`, `CHAT-P-FILE-006`, `CHAT-P-FILE-007`, `CHAT-P-FILE-008`, `CHAT-P-FILE-009` | docs/ARCHITECTURE.md | File Processing | P2 | parser/provenance/security integration | ADOPTED |
| `CHAT-P-FMT-001`, `CHAT-P-FMT-002`, `CHAT-P-FMT-003`, `CHAT-P-FMT-004`, `CHAT-P-FMT-005` | Issue #222 + docs/AI_RUNTIME.md | Response Formatting Policy | P1 | provider-neutral prompt/response contract tests | ADOPTED |
| `CHAT-P-GEN-001`, `CHAT-P-GEN-002`, `CHAT-P-GEN-003`, `CHAT-P-GEN-004`, `CHAT-P-GEN-005` | docs/ARCHITECTURE.md | Generated File Runtime | P3 | structural file validation + Media delivery | ADOPTED |
| `CHAT-P-IMG-001`, `CHAT-P-IMG-002`, `CHAT-P-IMG-003`, `CHAT-P-IMG-004` | Issue #222 + docs/AI_RUNTIME.md | Image capability flow | P3 | Job/Media/version/quote integration | ADOPTED |
| `CHAT-P-LIFE-001`, `CHAT-P-LIFE-002`, `CHAT-P-LIFE-003`, `CHAT-P-LIFE-004`, `CHAT-P-LIFE-005`, `CHAT-P-LIFE-006`, `CHAT-P-LIFE-007`, `CHAT-P-LIFE-008`, `CHAT-P-LIFE-009`, `CHAT-P-LIFE-010`, `CHAT-P-LIFE-011` | Issue #222 + docs/ARCHITECTURE.md | Conversation lifecycle | P1 | PostgreSQL lifecycle + browser recovery/idempotency | ADOPTED |
| `CHAT-P-MODEL-001`, `CHAT-P-MODEL-002`, `CHAT-P-MODEL-003`, `CHAT-P-MODEL-004` | docs/AI_RUNTIME.md + docs/ADMIN.md | Conversation model catalog | P4 | provider contract + effective-model tests | ADOPTED |
| `CHAT-P-NFR-005` | docs/UX.md + docs/MAINTAINABILITY.md | Release NFR | P1 | browser matrix + a11y + benchmark evidence | ADOPTED |
| `CHAT-P-NFR-001`, `CHAT-P-NFR-002`, `CHAT-P-NFR-003`, `CHAT-P-NFR-004` | docs/UX.md + docs/MAINTAINABILITY.md | Release NFR | P5 | browser matrix + a11y + benchmark evidence | ADOPTED |
| `CHAT-P-RENDER-001`, `CHAT-P-RENDER-002`, `CHAT-P-RENDER-003`, `CHAT-P-RENDER-004`, `CHAT-P-RENDER-005`, `CHAT-P-RENDER-006` | docs/UX.md | Renderer | P1 | renderer fixtures + stream torture + browser | ADOPTED |
| `CHAT-P-SEC-001`, `CHAT-P-SEC-002`, `CHAT-P-SEC-003`, `CHAT-P-SEC-004` | docs/ARCHITECTURE.md + docs/AI_RUNTIME.md | Chat security boundary | P5 | cross-account + prompt-injection negative tests | ADOPTED |
| `CHAT-P-SPEND-001`, `CHAT-P-SPEND-002`, `CHAT-P-SPEND-003`, `CHAT-P-SPEND-004`, `CHAT-P-SPEND-005`, `CHAT-P-SPEND-006`, `CHAT-P-SPEND-007` | docs/PRODUCT.md + docs/ARCHITECTURE.md | Spend Authority | P4 | funding race/idempotency/reconcile tests | ADOPTED |
| `CHAT-P-SRC-001`, `CHAT-P-SRC-002`, `CHAT-P-SRC-003` | docs/ARCHITECTURE.md + docs/UX.md | Structured Sources | P2 | source provenance + renderer/browser | ADOPTED |
| `CHAT-P-UI-001`, `CHAT-P-UI-002`, `CHAT-P-UI-003`, `CHAT-P-UI-004` | Issue #222 + docs/UX.md | Chat UI/UX | P1 | browser geometry + a11y E2E | ADOPTED |
| `ENG-AUDIT-001` | docs/MAINTAINABILITY.md | Maintenance cadence | each owning P1–P5 package + P5 final | package delta / structural audit report | ADOPTED |
| `ENG-CLEAN-001`, `ENG-CLEAN-002`, `ENG-CLEAN-003` | docs/MAINTAINABILITY.md | Garbage cleanup | each owning P1–P5 package + P5 final | consumer proof + preserved coverage | ADOPTED |
| `ENG-DEP-001`, `ENG-DEP-002` | docs/MAINTAINABILITY.md | Dependency hygiene | each owning P1–P5 package + P5 final | dependency/license/bundle/security checks | ADOPTED |
| `ENG-DOC-001`, `ENG-DOC-002`, `ENG-DOC-003`, `ENG-DOC-004`, `ENG-DOC-005` | docs/MAINTAINABILITY.md + docs/DOCS_SYSTEM.md | Documentation architecture | each owning P1–P5 package + P5 final | check_docs + context route checks | ADOPTED |
| `ENG-FILE-001`, `ENG-FILE-002`, `ENG-FILE-003`, `ENG-FILE-004` | docs/MAINTAINABILITY.md | File budgets | each owning P1–P5 package + P5 final | architecture size/headroom checks | ADOPTED |
| `ENG-MOD-001`, `ENG-MOD-002`, `ENG-MOD-003` | docs/MAINTAINABILITY.md | Module ownership | each owning P1–P5 package + P5 final | import/owner review + nearest tests | ADOPTED |
| `ENG-PERF-001`, `ENG-PERF-002` | docs/MAINTAINABILITY.md + docs/UX.md | Performance acceptance | each owning P1–P5 package + P5 final | versioned benchmark profile + exact-head report | ADOPTED |
| `ENG-SPLIT-001`, `ENG-SPLIT-002`, `ENG-SPLIT-003` | docs/MAINTAINABILITY.md | Split-before-growth | each owning P1–P5 package + P5 final | characterization tests + size check | ADOPTED |
| `ENG-TEMP-001`, `ENG-TEMP-002` | docs/MAINTAINABILITY.md | Temporary code lifecycle | each owning P1–P5 package + P5 final | owner/expiry audit | ADOPTED |
| `ENG-TEST-001`, `ENG-TEST-002` | docs/MAINTAINABILITY.md | Test hygiene | each owning P1–P5 package + P5 final | coverage mapping + quarantine owner/expiry | ADOPTED |

### 5.1. Coverage invariant

- В таблице присутствуют все MUST IDs Product/Architecture/Engineering review pack ровно один раз.
- SHOULD/MAY/DEFERRED не маскируются как acceptance blockers.
- При добавлении/удалении/смене gate любого MUST эта таблица обновляется тем же docs package.
- Adoption в canonical docs меняет status группы на `ADOPTED`; implementation status меняется только при привязанном test/evidence, а не по заявлению.
- Конкретные test paths/evidence IDs фиксируются при создании bounded implementation package; до этого test/evidence class задаёт обязательный тип доказательства и не считается `PASS`.

### 5.2. Platform Source/Delivery requirements

`PLAT-SRC-*`, `PLAT-DONOR-*`, `PLAT-VIS-*` и `PLAT-DEL-*` принадлежат отдельному `IZO_ASA_PLATFORM_SOURCE_DELIVERY_CONTRACT_v1.md` и имеют собственную adoption traceability там. Они **не меняют** утверждённый счётчик Chat v4 `193 MUST`; E0 обязан перенести их в platform canonical owners до начала нового product implementation package.

## 6. Current structural pressure

Действующий maintainability hard-limit production files — 12 KB / 300 lines, warning zone >80%.

На текущем Chat snapshot около warning threshold уже находятся:

### Backend

- `apps/api/izo/chat/catalog.py` — ~9.5 KB;
- `conversations.py` — ~9.5 KB;
- `provider.py` — ~9.3 KB;
- `execution.py` — ~9.1 KB;
- `service.py` — ~8.2 KB.

### Frontend

- `ChatComposer.tsx` — ~9.6 KB;
- `useChatRuntime.ts` — ~9.6 KB;
- `ChatComposer.css` — ~9.5 KB;
- `useChatPreflight.ts` — ~9.4 KB;
- `ChatCredentialPanel.tsx` — ~9.4 KB;
- `chatAttachments.ts` — ~9.0 KB;
- `ChatRuntime.css` — ~9.0 KB.

**Следствие:** P1/P2 нельзя реализовывать простым добавлением ещё сотен строк в эти owners. Первый соответствующий package должен спланировать split по ответственности.

---

## 7. Что не делать при внедрении

- не добавлять эти четыре review-документа как четыре новых permanent live specs рядом с существующими owners;
- не переписывать рабочий Chat целиком ради target folder tree;
- не сливать current #236 автоматически;
- не менять PLAN/CURRENT вручную вне state workflow;
- не превращать P1–P5 в один 100-file PR;
- не начинать Credits migration до принятого Spend Authority ADR;
- не строить full artifact editor до Generated File acceptance;
- не добавлять новые provider tools в Chat ProviderAdapter;
- не объявлять внешний ChatGPT/Claude UI вечным acceptance standard;
- не начинать новый Admin/Image/Gallery/Feed product package без `SOURCE_AUDIT` target+donor;
- не копировать крупный feature из `IZO_ASA` wholesale и не переносить donor auth/ledger/storage/provider ownership;
- не создавать dedicated Image/Video/Audio/3D backend вместо уже принятой Chat/shared capability.

---

## 8. Adoption Done

v4 считается корректно внедрённой в документационный контур, когда:

1. #222 — единственный canonical Chat product priority;
2. stable docs содержат только принадлежащие им факты;
3. owner issues не противоречат #222;
4. PLAN/CURRENT остаются единственным current state owner;
5. P1–P5 и requirement IDs можно связать с конкретными packages/tests;
6. `MAINTAINABILITY.md` содержит усиленный audit/cleanup cadence;
7. следующий product package не расширяет near-limit Chat owners без split;
8. docs/context checks проходят без увеличения budget ради PASS;
9. source hierarchy, donor classification и `NEW_DECISION_REQUIRED` gate приняты в canonical process docs;
10. `PRODUCT.md` однозначно показывает VISIBLE/FUNCTIONAL/ACCEPTED и следующий user-visible delivery stage;
11. Admin A1/A2/A3 и Chat-first specialist-tab sequencing приняты без создания второго roadmap/source of truth.