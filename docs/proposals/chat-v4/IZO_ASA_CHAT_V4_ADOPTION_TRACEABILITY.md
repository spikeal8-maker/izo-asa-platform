# IZO ASA Chat v4 — Adoption & Traceability Plan

**Назначение:** переходный документ для внедрения Product/Architecture/Maintenance v4 в существующий GitHub-контур.  
**Важно:** этот файл **не должен становиться новым постоянным `ROADMAP/NOW/MASTER_PLAN` в репозитории**. После принятия его решения распределяются по существующим owners: Issue #222/PRODUCT, ARCHITECTURE, AI_RUNTIME, ADMIN, UX, MAINTAINABILITY, local README, PLAN/CURRENT.

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
| `docs/MAINTAINABILITY.md` | Chat 3-package audit, 30-day backstop, temporary-code expiry, garbage policy |
| local Chat README | краткие live owners/invariants/tests после фактической структуры |
| `BLOCK_MAP/CONTEXT_MAP` | новые owners только по мере появления реального кода |

### Mutable state

- `PLAN.json`/`CURRENT.md` меняются только через действующий state-transition workflow после принятия exact-head checkpoint.
- CI evidence остаётся в `CHECKPOINTS.json`/reviews.

---

## 4. Рекомендуемая последовательность convergence

### E0 — Spec adoption only

Цель: принять v4 семантически, не менять product code.

1. owner подтверждает Product v4;
2. обновляется #222;
3. синхронизируются противоречащие owner issues;
4. stable docs получают только свои факты;
5. docs checks проходят;
6. current execution lineage не переписывается автоматически.

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

## 5. Requirement → owner traceability (initial)

| Product area | Stable owner | Existing issue / future package | Primary evidence |
| --- | --- | --- | --- |
| durable thread/request | ARCHITECTURE + Chat README | #87/#88 | PostgreSQL integration |
| branch/edit/regenerate | PRODUCT + ARCHITECTURE | #87/#88/#139 update | branch/attempt tests |
| context engine | ARCHITECTURE/AI_RUNTIME | #88 update | deterministic context cases |
| renderer | UX + #222 | #140 | dedicated renderer browser suite |
| clipboard/actions | UX | #139/#140 | serializer + browser clipboard |
| composer/model selection | UX/AI_RUNTIME | #141 | E2E + request snapshot |
| image input/vision | PRODUCT/AI_RUNTIME | current #236 + convergence | media→chat integration |
| file ingestion | ARCHITECTURE | new bounded owner package | parser/provenance tests |
| file generation | ARCHITECTURE | new tool/runtime package | structural file validation |
| image generation/edit | PRODUCT/AI_RUNTIME | new tool package | Job/Media/version tests |
| provider adapters | AI_RUNTIME | #88 / adapter packages | provider contract tests |
| Admin model policy | ADMIN | catalog/admin package | permission/audit tests |
| Daily/Premium/BYOK | PRODUCT + ARCHITECTURE | ADR + Credits/Entitlements package | financial/race/reconcile tests |
| maintenance/cleanup | MAINTAINABILITY | every package + audits | check_change/check_docs/audit report |

---

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
- не объявлять внешний ChatGPT/Claude UI вечным acceptance standard.

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
8. docs/context checks проходят без увеличения budget ради PASS.