# IZO ASA Platform — Source-First & Delivery Contract v1

**Статус:** APPROVED SOURCE SNAPSHOT · ADOPTED INTO CANONICAL OWNERS · NON-CANONICAL FOR FUTURE IMPLEMENTATION.
**Назначение:** provenance принятой Source-First/Donor/Delivery semantics.
**Связь с Chat v4:** этот snapshot не меняет принятую Chat v4 semantics.
**Live authority после E0:** `PRODUCT.md`, `MAINTAINABILITY.md`, `DOCS_SYSTEM.md`, `ADMIN.md`, `DEVELOPMENT.md` и профильные canonical owners; snapshot не является вторым ROADMAP/NOW.

---

## 1. Основной принцип

IZO ASA развивается **source-first** и **Chat-first**.

**Source-first:** coding-agent не проектирует пользовательское, архитектурное или операционное поведение с нуля, пока не доказано отсутствие применимого принятого источника.

**Chat-first:** новая AI-capability сначала должна иметь один end-to-end рабочий путь через общий Chat и shared domains. После acceptance соответствующей capability допускается отдельная специализированная вкладка, использующая те же Jobs/Media/Catalog/Spend/provider runtime, а не второй backend.

Исключения из «сначала вкладка Chat, потом всё остальное»:
- Admin — control plane, необходимый для управления моделями, доступом, стоимостью, jobs/media/audit и потому частично обязателен до финального Chat acceptance;
- Gallery — asset surface, а не отдельная AI-capability;
- Feed — publication surface, а не отдельная AI-capability.

---

## 2. Нормативная иерархия источников

Каждый package имеет `SOURCE_AUDIT`, но глубина audit пропорциональна semantic scope. Когда требуется поиск источников, агент идёт **в этом порядке**:

1. действующие canonical owners target-репозитория;
2. фактический код/tests target-репозитория на fresh source SHA;
3. APPROVED specs/ADR/accepted review contracts target-репозитория;
4. donor `spikeal8-maker/IZO_ASA` на fresh donor SHA;
5. внешние benchmark/reference products или официальные внешние contracts, если они действительно нужны;
6. только при отсутствии достаточного решения — `NEW_DECISION`.

При конфликте действует приоритет:

```text
approved current IZO ASA canonical contract
>
approved architecture/security/governance
>
current target implementation evidence
>
donor IZO_ASA behavior/test idea
>
external UX/product reference
>
implementer proposal
```

Текущий код не отменяет более новый approved target contract: в таком случае это implementation gap, а не повод вернуть старую семантику.

### Requirements

- **PLAT-SRC-001 [MUST]** — каждый package до product/code design содержит `SOURCE_AUDIT`; его режим и глубина пропорциональны semantic scope по §3.
- **PLAT-SRC-002 [MUST]** — применимый donor/existing target нельзя игнорировать и затем выдавать отсутствие поиска за «решения нет»; для доказанно semantics-neutral `BOUNDED_LOCAL` donor разрешено отметить `NOT_REQUIRED` только с причиной по §3.
- **PLAT-SRC-003 [MUST]** — implementer не выбирает новую observable product semantics молча; неизвестное решение маркируется `NEW_DECISION_REQUIRED`.
- **PLAT-SRC-004 [MUST]** — `NEW_DECISION_REQUIRED` блокирует реализацию затронутой semantics до owner/approved-contract decision; не блокирует независимые уже определённые части package.
- **PLAT-SRC-005 [MUST]** — source audit фиксирует обязательные поля выбранного режима, применимые repository/exact SHA/ref/paths/symbols, найденную semantics, conflicts и принятое решение так, чтобы audit можно было повторить из GitHub.
- **PLAT-SRC-006 [MUST]** — внешний ChatGPT/Claude/другой продукт может быть исследовательским benchmark, но не живой нормативной зависимостью. Выбранное поведение фиксируется в IZO ASA contract.
- **PLAT-SRC-007 [MUST]** — production data, users, secrets, credentials и private runtime state никогда не используются как donor-content для переноса.
- **PLAT-SRC-008 [MUST]** — fresh target SHA обязателен для любого `SOURCE_AUDIT`; fresh donor SHA обязателен, когда donor comparison/reuse входит в audit scope. Старый snapshot/SHA не считается fresh автоматически.
- **PLAT-SRC-009 [MUST]** — если current target уже имеет более безопасный/новый owner, donor не создаёт второй source of truth.
- **PLAT-SRC-010 [MUST]** — handoff хранит source-audit/provenance в GitHub, чтобы следующий агент мог повторить решение без истории чата.

---

## 3. Обязательный SOURCE_AUDIT до реализации

Каждый package имеет ровно один явно указанный режим source audit:

```text
SOURCE_AUDIT_MODE
FULL
```

или:

```text
SOURCE_AUDIT_MODE
BOUNDED_LOCAL
```

### 3.1. `FULL`

`FULL` обязателен, если package меняет хотя бы одно из следующего:

- observable product behavior;
- product/domain capability;
- domain/data ownership;
- security/auth semantics;
- Credits/pricing/spend semantics;
- provider semantics;
- storage/lifecycle semantics;
- publication/privacy behavior;
- major UX workflow;
- dedicated product surface;
- donor reuse.

Для product/domain work в Admin, Image, Gallery и Feed всегда используется `FULL`, включая требования `PLAT-DEL-010`.

Минимальный machine/human-readable отчёт:

```text
SOURCE_AUDIT
SOURCE_AUDIT_MODE
FULL

TARGET_REPO
TARGET_SHA
TARGET_CANONICAL_OWNERS
TARGET_CODE
TARGET_TESTS

DONOR_REPO
DONOR_SHA
DONOR_PATHS
DONOR_BEHAVIOR

EXTERNAL_REFERENCES
<none or exact references>

CONFLICTS
<none or exact conflicts>

DECISIONS
<classification per donor item>

NEW_DECISIONS_REQUIRED
<none or exact decisions>

IMPLEMENTATION_SCOPE
<only gaps that remain>
```

### 3.2. `BOUNDED_LOCAL`

`BOUNDED_LOCAL` допустим только если одновременно истинны все условия:

- change small/local;
- observable semantics unchanged;
- domain/owner boundary unchanged;
- security/auth unchanged;
- pricing/Credits/spend unchanged;
- storage/persistence unchanged;
- donor reuse отсутствует;
- canonical target owner уже однозначно определяет поведение.

Минимальный отчёт:

```text
SOURCE_AUDIT
SOURCE_AUDIT_MODE
BOUNDED_LOCAL

TARGET_SHA
TARGET_OWNER
TARGET_PATHS
NEAREST_TESTS

OBSERVABLE_SEMANTICS_CHANGED
NO

OWNER_BOUNDARY_CHANGED
NO

DONOR_RESEARCH
NOT_REQUIRED

DONOR_SHA
NOT_REQUIRED

REASON
semantics-preserving local change
```

`DONOR_RESEARCH = NOT_REQUIRED` и `DONOR_SHA = NOT_REQUIRED` допустимы только при выполнении всех условий `BOUNDED_LOCAL` и с указанной причиной. Такой режим означает, что audit остановился на достаточном canonical target owner/code/tests; он не разрешает придумывать новое behavior.

Если в `BOUNDED_LOCAL` обнаружены new observable semantics, ambiguous owner, product decision или donor reuse proposal, bounded mode прекращается. Дальше package обязан перейти в `FULL` либо вернуть `NEW_DECISION_REQUIRED` для затронутой semantics.

Если `NEW_DECISIONS_REQUIRED != none`, агент не должен «закрыть» эти решения кодом.

---

## 4. Donor `spikeal8-maker/IZO_ASA`

Donor используется как источник **проверенных продуктовых решений, UX, acceptance cases, test ideas и ограниченных безопасных assets**, но не как кодовая база для wholesale transplant.

Каждый переносимый элемент получает ровно одну классификацию:

| Класс | Значение |
| --- | --- |
| `ADOPT_BEHAVIOR` | поведение/UX принимается как target semantics после проверки на конфликт |
| `PORT_TEST` | переносится test/acceptance idea, адаптированная к новой архитектуре |
| `PORT_ASSET` | переносится безопасный reusable asset, если license/provenance/ownership допустимы |
| `REIMPLEMENT` | продуктовая идея сохраняется, код пишется заново на target domains |
| `REJECT` | donor-поведение/код противоречит target contract, security или maintainability |

### Requirements

- **PLAT-DONOR-001 [MUST]** — запрещён wholesale copy каталога/feature из `IZO_ASA` без item-level classification.
- **PLAT-DONOR-002 [MUST]** — donor auth/session/ledger/provider-secret/storage ownership не переносится автоматически.
- **PLAT-DONOR-003 [MUST]** — donor schema/migration не копируется без отдельной target data-model/ADR проверки.
- **PLAT-DONOR-004 [MUST]** — giant/monolithic donor component не переносится как новый target owner; behavior/test может быть принят, implementation обязан соблюдать current file/module budgets.
- **PLAT-DONOR-005 [MUST]** — donor test может быть ported только если target semantics совпадает; старый test не делает старое поведение автоматически правильным.
- **PLAT-DONOR-006 [MUST]** — при конфликте approved target behavior побеждает donor.
- **PLAT-DONOR-007 [MUST]** — donor decision записывает `repo + exact SHA + path/symbol + classification + reason + target owner`.
- **PLAT-DONOR-008 [MUST]** — copy source-code допускается только как узкий доказанный reuse, если dependency/security/license/size/ownership подходят target; default для старых крупных features — reimplementation.
- **PLAT-DONOR-009 [MUST]** — после переноса donor не остаётся runtime/documentation dependency: canonical truth живёт в target repository.

---

## 5. Donor discovery map

Snapshot для подготовки этого contract:

```text
DONOR_REPO
spikeal8-maker/IZO_ASA

DONOR_MAIN_AT_AUDIT
89d6d94093fdb6d2a52cacd269e15fce342a155a
```

Этот SHA — audit evidence, а не вечный ref. Каждый будущий package получает fresh donor SHA.

| Area | High-value donor sources | Что искать |
| --- | --- | --- |
| Admin | `docs/admin-panel-guide.md`, `docs/context/admin-control-center.md`, `frontend/src/AdminApp.tsx`, `frontend/src/admin*.tsx`, admin E2E/tests | navigation, CRM dossier, models, publication, tariffs, payments, notifications, social, mail, bots, logs, trusted mutations |
| Image | `docs/phone-image-implementation-20260824.md`, `docs/context/image-generation.md`, `frontend/src/phone/features/image/*`, image tests | prompt/model/aspect/resolution, references, styles, drawing, mask/inpaint/outpaint/remove-bg/face reference, viewer/history/publish |
| Gallery | `docs/gallery-current-product-plan.md`, `backend/app/services/gallery_*.py`, gallery static UI/tests | pagination/search/filter, viewer, favorite, delete/publish/use-as, generated/uploaded picker |
| Feed | `docs/feed-current-product-plan.md`, `docs/feed-v3-implementation-20260717.md`, `backend/app/services/feed_*.py`, feed UI/tests | guest public read, cursor pagination, search, derivatives, publish/moderation, reactions/save/follow/hide/report/remix |
| Chat | `docs/chat-assistant-contract.md`, old desktop/phone Chat + tests | research/test ideas only; APPROVED Chat v4 is higher authority |

Known example:

```text
old Gallery silent tariff auto-eviction
→ REJECT
```

Target PRODUCT storage semantics block new bytes when full and do not silently delete saved user work.

---

## 6. Delivery states: VISIBLE / FUNCTIONAL / ACCEPTED

Каждая крупная поверхность имеет три разных состояния.

- **VISIBLE** — route/surface можно показать; это не доказательство backend/runtime readiness.
- **FUNCTIONAL** — заявленный end-to-end path реально работает на target contracts и не является fixture/demo-only.
- **ACCEPTED** — required tests/review/CI/restart/security/browser/live evidence соответствующего gate пройдены.

### Requirements

- **PLAT-VIS-001 [MUST]** — UI не маркируется готовым только потому, что route видим.
- **PLAT-VIS-002 [MUST]** — presentation/demo surface честно помечается как presentation и не имитирует реальные users/publications/paid provider results.
- **PLAT-VIS-003 [MUST]** — product status/report различает `VISIBLE`, `FUNCTIONAL`, `ACCEPTED`.
- **PLAT-VIS-004 [MUST]** — пользовательское обещание/launch использует только ACCEPTED scope либо явно обозначенный preview/beta scope.

---

## 7. Platform delivery order

### Stage 0 — E0/E1: docs + current-package closure

**Видно пользователю:** нового продукта не обещается.  
**Цель:** canonical adoption approved Chat v4 + source/delivery policy; отдельно завершить/freeze текущий Chat package по governance.

```text
VISIBLE     existing surfaces only
FUNCTIONAL  existing accepted/runtime facts only
ACCEPTED    E0 docs adoption + E1 current lineage reconciliation
```

### Stage 1 — Chat P1: Conversation Experience

Пользователь получает полноценный современный text Chat:
- history/search/new/rename/archive/restore;
- streaming/Stop/retry/regenerate/edit/branches;
- deterministic Context Engine;
- model selector;
- safe rich renderer, code/tables/math;
- Copy / Copy Markdown;
- desktop/mobile/reload/restart semantics соответствующего gate.

```text
VISIBLE     Chat workspace
FUNCTIONAL  P1 text conversation paths
ACCEPTED    P1 gate
```

### Stage 2 — Chat P2: Multimodal Input

Через Chat принимаются и анализируются approved inputs:
- images;
- PDF/DOCX;
- XLSX/CSV/TSV;
- TXT/MD/HTML/JSON/XML/YAML/source files;
- audio through approved ASR;
- truthful unsupported states.

```text
VISIBLE     attachment/file controls
FUNCTIONAL  supported format × operation matrix
ACCEPTED    P2 gate
```

### Stage 3 — Chat P3: Creation & Tools

Через Chat:
- создаются реальные downloadable PDF/DOCX/XLSX/CSV/TSV/HTML/MD/TXT/JSON и accepted optional formats;
- работает server Tool Orchestrator;
- работает image generation;
- image edit создаёт derived asset/version;
- общие Jobs/Media используются как source of truth.

```text
VISIBLE     generated file/image result blocks
FUNCTIONAL  real server-side creation/tool/image paths
ACCEPTED    P3 gate
```

### Stage 4 — Chat P4 + Admin A1: Product Control

До P4/P5 acceptance staff получает достаточный control plane:

- users/account state;
- Access/permissions;
- model/provider candidates;
- publish/disable/effective model;
- provider/credential metadata;
- pricing;
- Daily/Premium/BYOK policy;
- Credits/grants/ledger views;
- jobs/reconcile;
- media metadata;
- audit/system health needed by Chat.

Admin A1 не обязан включать весь будущий operational control center.

```text
VISIBLE     staff-only Admin A1 surfaces as owners land
FUNCTIONAL  server-authorized control of Chat product
ACCEPTED    P4 Admin/effective-model/spend gates
```

### Stage 5 — Chat P5: Release Acceptance

Security/performance/a11y/restart/browser/package/live gates.

После этого:

```text
CHAT_PRODUCT_V1_ACCEPTED
```

Только после этого specialized AI tabs становятся следующим основным product-development priority.

---

## 8. Специализированные поверхности после Chat Product V1

### I1 — Image Workspace V1

Использует уже принятую P3 image capability, Jobs/Media/Catalog/Spend.

Минимальный target:
- prompt;
- model;
- references/input picker;
- aspect/size/count;
- quote/confirmation;
- progress/result;
- download/use-as;
- responsive desktop/mobile.

Donor discovery обязателен по §5.

### G1 — Gallery V1

Provider-neutral private asset surface:
- real previews/thumbnails;
- type/filter/sort/search;
- pagination;
- detail/fullscreen viewer;
- zoom/download;
- use-as-input;
- favorite where product policy accepts it;
- explicit delete with dependency explanation;
- lineage/derived-from;
- storage usage.

Никакой второй файловой базы.

### F1 — Feed V1

Public publication surface:
- guest public read;
- public derivative, never private original fallback;
- cursor pagination/search/filter;
- publication detail;
- publish/unpublish;
- moderation state/report;
- staff moderation;
- basic author public profile.

Social expansion (follow/save/like/remix/challenges) — отдельный bounded follow-up, если не включён owner decision.

### I2 — Image Editor

После I1/G1 foundation:
- mask/sketch;
- inpaint/outpaint;
- remove background;
- accepted references/face-reference semantics;
- undo/preview;
- derived asset version; original never overwritten.

---

## 9. Future modality rule

После `CHAT_PRODUCT_V1_ACCEPTED` каждая новая крупная AI-modality идёт в два шага:

```text
Capability-in-Chat acceptance
→
Dedicated tab acceptance
```

### Video

```text
VC1 — video capability through Chat
→ V1 — /video workspace
```

### Audio

```text
AC1 — audio/TTS/music capability through Chat
→ A1 — /audio workspace
```

ASR input, уже использованный в Chat P2, не означает принятую full Audio creation product.

### 3D

```text
DC1 — 3D capability through Chat
→ D1 — /3d workspace
```

### Requirements

- **PLAT-DEL-001 [MUST]** — до `CHAT_PRODUCT_V1_ACCEPTED` новые dedicated AI tabs не становятся основным development priority вместо незакрытого P1–P5.
- **PLAT-DEL-002 [MUST]** — Image dedicated workspace использует P3 shared image capability, а не второй generation backend.
- **PLAT-DEL-003 [MUST]** — Video/Audio/3D creation capability сначала принимается через Chat, затем получает dedicated workspace.
- **PLAT-DEL-004 [MUST]** — Admin A1 является supporting prerequisite P4/P5, а не пост-Chat optional tab.
- **PLAT-DEL-005 [MUST]** — Gallery использует shared Media/assets; Feed использует Publication/public derivative ownership, не private-original shortcuts.
- **PLAT-DEL-006 [MUST]** — Feed real-user/publication behavior не считается FUNCTIONAL до FEED contract/backend; presentation cards не являются fake publications.
- **PLAT-DEL-007 [MUST]** — каждая dedicated surface имеет собственный acceptance gate и не становится ACCEPTED по факту существования общей capability.
- **PLAT-DEL-008 [MUST]** — specialist tab может появиться визуально раньше acceptance только как честно маркированный preview/disabled surface; это не меняет delivery priority.
- **PLAT-DEL-009 [MUST]** — shared Accounts/Credits/Jobs/Media/Catalog/Spend/Provider ownership повторно не реализуется в specialist tabs.
- **PLAT-DEL-010 [MUST]** — Admin/Feed/Gallery/Image package перед кодом проходит donor source audit.
- **PLAT-DEL-011 [MUST]** — platform delivery report всегда отвечает «что видно сейчас / что реально работает / что принято / что появится следующим».
- **PLAT-DEL-012 [MUST]** — календарные сроки не придумываются агентом; если owner не утвердил дату, sequencing задаётся acceptance gates и dependencies, а не вымышленной датой.

---

## 10. Admin delivery layers

Чтобы «Admin есть» не означало один огромный финальный package:

### Admin A1 — Chat control plane

Обязателен к P4/P5:
- Users/account state;
- Access;
- models/providers/catalog publication;
- credentials metadata/binding controls;
- pricing;
- Daily/Premium/BYOK product controls;
- Credits/grants;
- Chat-related jobs/media;
- audit/system status.

### Admin A2 — Image/Gallery/Feed control

Появляется вместе с соответствующими accepted products:
- image capability/model management;
- Media review;
- publication moderation;
- reports;
- storage/public derivative policy.

### Admin A3 — Extended operations

Отдельные bounded products:
- payments;
- notifications;
- mail;
- Telegram/MAX bots;
- social delivery;
- support;
- workers;
- advanced analytics.

Старый donor Admin предоставляет поведенческие/test references, но target permissions/domain ownership остаются новыми.

---

## 11. Definition of Done source-first package

Package не может получить technical/product PASS, если:

1. отсутствует `SOURCE_AUDIT` либо не указан `SOURCE_AUDIT_MODE`;
2. выбранный `FULL` или `BOUNDED_LOCAL` не соответствует semantic scope §3;
3. `BOUNDED_LOCAL` заявляет donor `NOT_REQUIRED` без выполнения всех bounded-условий и причины;
4. применимый donor/target source проигнорирован без причины;
5. есть скрытый `NEW_DECISION_REQUIRED`;
6. donor code скопирован без classification/provenance;
7. donor behavior конфликтует с approved target contract;
8. specialist tab создаёт второй Jobs/Media/Credits/Catalog/provider owner;
9. status «готово» не различает VISIBLE/FUNCTIONAL/ACCEPTED;
10. handoff не позволяет другому агенту восстановить source reasoning из GitHub.

---

## 12. Adoption routing

После approval этого contract:

| Fact | Canonical owner |
| --- | --- |
| Platform delivery order, VISIBLE/FUNCTIONAL/ACCEPTED | `docs/PRODUCT.md` |
| Source hierarchy, donor classification, NEW_DECISION gate | `docs/MAINTAINABILITY.md` |
| Provenance/handoff/source references | `docs/DOCS_SYSTEM.md` |
| Admin A1/A2/A3 product-control boundaries | `docs/ADMIN.md` |
| Chat P1–P5 semantics | existing Chat v4 owners |
| Current package/order/status | `PLAN.json` / `CURRENT.md` only |

Proposal snapshot/donor SHA остаются provenance и не переносятся как mutable facts в stable docs.

---

## 13. Platform contract traceability

Status `ADOPTED` означает canonical docs adoption в E0; это не `IMPLEMENTED` и не runtime/product acceptance.

| Requirement group | Canonical owner after adoption | Gate/evidence | Status |
| --- | --- | --- | --- |
| `PLAT-SRC-001..010` | MAINTAINABILITY + DOCS_SYSTEM | source-audit validator/review + GitHub handoff evidence | ADOPTED |
| `PLAT-DONOR-001..009` | MAINTAINABILITY | donor classification/provenance review | ADOPTED |
| `PLAT-VIS-001..004` | PRODUCT | product status/acceptance report | ADOPTED |
| `PLAT-DEL-001..003` | PRODUCT + AI_RUNTIME reference | delivery dependency/acceptance review | ADOPTED |
| `PLAT-DEL-004` | PRODUCT + ADMIN | P4/P5 admin acceptance evidence | ADOPTED |
| `PLAT-DEL-005` | PRODUCT + ARCHITECTURE | shared Media / Publication ownership boundary | ADOPTED |
| `PLAT-DEL-006` | PRODUCT | Feed FUNCTIONAL semantics / real-backend acceptance | ADOPTED |
| `PLAT-DEL-007` | PRODUCT | dedicated surface acceptance gate | ADOPTED |
| `PLAT-DEL-008` | PRODUCT | preview / VISIBLE / ACCEPTED semantics review | ADOPTED |
| `PLAT-DEL-009` | ARCHITECTURE | duplicate-domain-owner prohibition / architecture boundary evidence | ADOPTED |
| `PLAT-DEL-010` | MAINTAINABILITY | donor SOURCE_AUDIT policy; provenance/handoff evidence is recorded through DOCS_SYSTEM without creating a second normative owner | ADOPTED |
| `PLAT-DEL-011..012` | PRODUCT + DOCS_SYSTEM | delivery report/docs review | ADOPTED |

No platform requirement in this document is `IMPLEMENTED` merely because this proposal exists.
