# IZO ASA Chat — Engineering, File Architecture & Maintenance Contract v4

**Статус:** APPROVED SOURCE SNAPSHOT · ADOPTED INTO CANONICAL OWNERS · NON-CANONICAL FOR FUTURE IMPLEMENTATION.
**Live authority после E0:** `docs/MAINTAINABILITY.md` и связанные canonical process owners. Этот snapshot сохраняет approved provenance, но не является default implementation context.

Этот документ не является roadmap и не хранит current SHA/PR.

---

## 1. Наследуем действующие бюджеты репозитория

Для handwritten production code (`apps/api/izo/**/*.py`, `apps/web/src/**/*.{ts,tsx,css}`):

- целевой размер: **≤ 8 KB** и обычно **≤ 200 строк**;
- warning zone: **>80% hard-limit**;
- hard-limit: **≤12 KB и ≤300 строк**.

Для tests/tools/e2e/acceptance/migrations:

- целевой размер: **≤12 KB**;
- warning zone: **>80% hard-limit**;
- hard-limit: **≤16 KB и ≤350 строк**.

**ENG-FILE-001 [MUST]** — hard-limit не повышается после failure ради зелёного CI.  
**ENG-FILE-002 [MUST]** — near-limit handwritten owner не увеличивается существенной новой ответственностью без split.  
**ENG-FILE-003 [MUST]** — новый handwritten file не создаётся сразу в warning zone.  
**ENG-FILE-004 [MUST]** — generated contracts/lockfiles не режутся искусственно ради лимита.

---

## 2. Split-before-growth

Перед началом package агент обязан проверить headroom всех изменяемых owner-files.

### Split обязателен до feature-кода, если выполняется хотя бы одно:

1. файл уже в warning zone и package добавит новую ответственность;
2. компонент одновременно владеет network + complex state + presentation;
3. backend модуль одновременно владеет HTTP + persistence + provider transport + policy;
4. stylesheet обслуживает несвязанные blocks и продолжает расти;
5. test-file стал местом несвязанных сценариев и приближается к auxiliary limit;
6. следующий package без split почти гарантированно приблизит hard-limit.

**ENG-SPLIT-001 [MUST]** — split сохраняет observable behavior и имеет characterization/affected tests.  
**ENG-SPLIT-002 [MUST]** — split производится по owner/responsibility, а не механическим `part1.py/part2.py`.  
**ENG-SPLIT-003 [MUST]** — после split старый module не остаётся вторым живым owner той же логики.

---

## 3. Один файл — одна основная причина изменения

Хороший owner-file отвечает на один тип изменений.

Примеры правильного разделения:

- `context_builder` меняется при правилах контекста, а не при CSS;
- `provider_openrouter` меняется при OpenRouter transport, а не при Admin pricing;
- `clipboardSerializer` меняется при copy semantics, а не при React toolbar layout;
- `CodeBlock` меняется при code presentation, а не при thread pagination;
- `Spend Authority` меняется при funding policy, а не при provider JSON parser.

**ENG-MOD-001 [MUST]** — название/расположение файла отражает responsibility.  
**ENG-MOD-002 [MUST]** — общий `utils.py/ts` не становится свалкой domain logic. Pure helper переносится в shared только при доказанном повторном consumer.  
**ENG-MOD-003 [MUST]** — новый абстрактный слой не создаётся «на будущее» без текущего consumer/test.

---

## 4. Документационная архитектура

Действующий `DOCS_SYSTEM.md` сохраняется. Один факт имеет одного live owner.

| Факт | Live owner |
| --- | --- |
| Product behavior Chat | canonical Chat issue / `PRODUCT.md` summary |
| Visual/interaction rules | `UX.md` + local Chat README |
| Domain/data/import boundaries | `ARCHITECTURE.md` |
| Provider/runtime/credentials | `AI_RUNTIME.md` |
| Admin/catalog/permissions | `ADMIN.md` |
| File/context/scope budgets, audits | `MAINTAINABILITY.md` |
| Current package/branch | `PLAN.json`/`CURRENT.md` |
| CI/checkpoint evidence | `CHECKPOINTS.json` |
| Package evidence | `reviews/<ID>.md` |

**ENG-DOC-001 [MUST]** — не создавать второй `MASTER_PLAN/ROADMAP/NOW`.  
**ENG-DOC-002 [MUST]** — stable/local docs не содержат mutable SHA/PR/working branch.  
**ENG-DOC-003 [MUST]** — local README — короткий ownership contract, не история проекта.  
**ENG-DOC-004 [MUST]** — старые планы/evidence перемещаются в `history/`/`reviews/`, а не копируются в live docs.  
**ENG-DOC-005 [MUST]** — при изменении owner/import boundary обновляются route/block maps и nearest tests.

---

## 5. Cadence оптимизации

Периодическая оптимизация — обязательная часть разработки, но не должна постоянно останавливать продукт.

### 5.1. Каждый package — Maintenance Delta

Перед freeze каждого package:

- размеры/строки изменённых handwritten files;
- предупреждения >80% hard-limit;
- новые responsibilities/import edges;
- context route bytes;
- local docs bytes;
- dependency additions/removals;
- новые TODO/feature flags/temp paths;
- dead/obsolete code, созданный этим package;
- self-review: стала ли следующая правка дороже.

**ENG-AUDIT-001 [MUST]** — package не получает technical pass, если сам создал avoidable structural debt или giant file.

### 5.2. Каждые 3 завершённых Chat product packages — Chat Structural Audit

Проверяется только активный Chat-контур:

1. top Chat frontend/backend files по bytes/lines;
2. near-limit owners;
3. duplicate responsibilities;
4. orphan CSS/selectors/components/hooks;
5. stale feature flags/temporary compatibility paths;
6. duplicate API clients/adapters;
7. renderer/tool/file dependency growth;
8. slow/duplicated Chat tests;
9. local docs/context route drift;
10. dead endpoints/contracts/types.

Если audit выявляет долг, который безопасно исправить в следующем product package — он входит в его pre-work. Отдельный maintenance package создаётся только если долг самостоятельный/high-risk.

### 5.3. Каждые 5 завершённых product packages — Repository Full Audit

Сохраняется уже действующее правило `MAINTAINABILITY.md`: top handwritten files, routes/context, local-doc budgets, stale docs, map/shard growth, duplicated ownership instructions, tools/workflows near limits.

### 5.4. Временной backstop

Если активная разработка Chat идёт **30 календарных дней**, но не набралось 3 завершённых Chat packages, выполняется targeted Chat Structural Audit.

### 5.5. Threshold-triggered audit

Audit выполняется немедленно, независимо от cadence, если:

- два или более Chat production files вошли в warning zone;
- scope package >40 files;
- новый package требует третью временную compatibility path одного owner;
- test suite заметно замедлилась из-за дублирования/монолита;
- один и тот же факт описан в двух live docs;
- Context route превышает budget;
- новая capability требует нарушить import/domain boundary.

---

## 6. Garbage cleanup policy

### 6.1. Что считается мусором

- dead production code без reachable consumer;
- просроченный temporary compatibility code после migration gate;
- unused imports/dependencies;
- orphan CSS classes/components/hooks;
- obsolete feature flags/experiments;
- duplicate API clients/provider adapters;
- test fixtures, больше не используемые ни одним test;
- stale generated artifacts, screenshots, local exports, backup files, debug dumps;
- TODO/FIXME, утратившие owner/issue;
- live docs с историей старых веток/SHA;
- дублирование одних и тех же invariants в нескольких live docs.

### 6.2. Что нельзя удалять как «мусор» автоматически

- принятые database migrations;
- immutable ledger/audit/checkpoint evidence;
- user Media/Artifacts;
- `docs/history/`/`docs/reviews/` provenance без retention policy;
- compatibility path, пока живой consumer не мигрирован и не доказан;
- security/recovery tests только потому, что они медленные;
- старый contract/version, пока supported persisted data/replay может на него ссылаться.

**ENG-CLEAN-001 [MUST]** — удаление production path требует доказательства отсутствия consumer или завершённой migration.  
**ENG-CLEAN-002 [MUST]** — garbage cleanup не использует `git reset --hard`, volume prune, удаление чужого WIP или пользовательских данных.  
**ENG-CLEAN-003 [MUST]** — «очистить тесты» не означает ослабить acceptance; дубли могут объединяться только при сохранённом coverage.

---

## 7. Temporary code имеет срок жизни

Каждый temporary bridge/feature flag/dual-read/dual-write содержит:

- owner package/issue;
- причину;
- condition удаления;
- не позднее какого acceptance gate его надо удалить.

**ENG-TEMP-001 [MUST]** — бессрочный `TODO remove later` запрещён в accepted production path.  
**ENG-TEMP-002 [MUST]** — если temporary code пережил два последующих product packages после planned expiry, следующий package блокируется на решение: удалить, formally extend с причиной, либо выделить maintenance package.

---

## 8. Dependency hygiene

Новая runtime dependency допускается только если:

1. решает реальный current requirement;
2. лицензия/maintenance/security приемлемы;
3. не дублирует уже установленный полноценный framework;
4. bundle/runtime cost измерен там, где существенен;
5. nearest tests доказывают использование.

Для renderer особенно запрещается одновременно тащить несколько перекрывающихся Markdown/math/highlight frameworks без ADR.

**ENG-DEP-001 [MUST]** — unused dependency удаляется в ближайший safe cleanup package.  
**ENG-DEP-002 [MUST]** — major dependency update не смешивается с несвязанным feature без необходимости.

---

## 9. Test architecture и её чистка

- тесты разделяются по owner/scenario, а не растут одним `chat-all.spec.ts`;
- deterministic fake transport обязателен для CI;
- live provider smoke отдельно;
- race/idempotency/restart/security cases не удаляются ради скорости;
- redundant viewport cases могут параметризоваться, если semantic coverage сохраняется.

**ENG-TEST-001 [MUST]** — при удалении/объединении test необходимо указать, какой оставшийся test покрывает прежний invariant.  
**ENG-TEST-002 [MUST]** — flaky test чинится или получает воспроизводимый quarantine с owner/expiry; permanent ignore без owner запрещён.

---


## 10. Performance debt и измеримая acceptance

Каждый Chat Structural Audit проверяет:

- full-thread re-render/reparse patterns;
- large dependency bundles;
- unnecessary provider/catalog fetches;
- N+1 history/file reads;
- leaked Object URLs/subscriptions/AbortControllers;
- oversized DOM history без pagination/virtualization;
- long synchronous parser work в main UI thread.

Chat performance evidence разделяет:

```text
provider queue / TTFT / generation latency
!=
IZO ASA platform + browser rendering overhead
```

До P1 acceptance владелец фиксирует versioned benchmark profile с численными thresholds; implementer не придумывает их после измерения ради PASS. Profile содержит baseline device class, browser, thread/message size, stream rate, measurement points и p95/p99 там, где percentile имеет смысл. Минимальные измерения: input responsiveness during streaming, chunk→render overhead, large-thread open, scroll stability, large code/table render и memory/DOM growth. До owner-approved numeric profile соответствующий performance gate = `BLOCKED`.

**ENG-PERF-001 [MUST]** — benchmark report отдельно показывает provider latency и platform/UI overhead и связывается с exact build/source checkpoint.  
**ENG-PERF-002 [MUST]** — performance threshold нельзя ослаблять после failure без отдельного owner/architecture decision с причиной; оптимизация делается по profile/measurement, не по необоснованным микрооптимизациям.

---

## 11. Current pressure points (не переносить в stable repo docs)

На snapshot, проверенном при подготовке v4, несколько Chat files уже близки к warning boundary действующего 12 KB production hard-limit: backend `catalog.py`, `conversations.py`, `provider.py`, `execution.py`; frontend `ChatComposer.tsx`, `useChatRuntime.ts`, `useChatPreflight.ts`, `ChatCredentialPanel.tsx`, `ChatRuntime.css` и др. Это означает: следующий существенный renderer/files/tools growth должен планировать split, а не продолжать расширять текущие owner-файлы.

Этот раздел — evidence для adoption plan; в канонический `MAINTAINABILITY.md` не нужно переносить конкретные filenames/размеры как вечные факты.

---

## 12. Definition of Done package после усиления v4

Package не получает `technical_pass`, если:

- изменённый near-limit owner вырос без обоснованного split;
- появилась новая owner responsibility без route/test;
- временный duplicate path не имеет expiry;
- добавлена unused/duplicate dependency;
- local docs дублируют mutable/current state;
- мусор, созданный package, оставлен «на потом» без owner;
- high-risk package нарушает review gate;
- CI стал зелёным после ослабления tests/limits;
- изменение заметно повышает стоимость следующей правки без зафиксированного архитектурного решения.