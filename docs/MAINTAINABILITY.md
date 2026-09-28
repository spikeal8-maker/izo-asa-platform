# Сопровождаемость и экономика агентской разработки · IZO ASA

Статус: каноническое ТЗ на качество структуры разработки. Этот документ не является roadmap и не хранит текущие SHA/PR.
Текущий пакет и ветка находятся только в `PLAN.json`/`CURRENT.md`.

## 1. Цель

Проект должен оставаться дешёвым для изменения человеком и coding-агентом при росте функциональности.
Маленькая правка не должна требовать чтения десятков файлов, больших спецификаций или монолитных модулей.
Рост продукта не является основанием повышать лимиты: при достижении бюджета ответственность разделяется.

Критерий качества — не только зелёный CI. Требуется одновременно:
- маленькие handwritten-файлы;
- маленький начальный контекст;
- явный owner каждого блока;
- конечный scope изменения;
- отсутствие дублирующих live-документов;
- проверяемая связь package → diff → tests → CI evidence;
- отсутствие скрытого роста стоимости следующей правки.

## 2. Бюджеты handwritten-кода

### Production
`apps/api/izo/**/*.{py}` и `apps/web/src/**/*.{ts,tsx,css}`:
- целевой размер: ≤ 8 KB и обычно ≤ 200 строк;
- зона предупреждения: > 80% hard-limit;
- hard-limit: ≤ 12 KB и ≤ 300 строк.

### Вспомогательный handwritten code
`tests/**/*.py`, `tools/**/*.py`, `apps/web/e2e/**/*.ts`, `apps/web/acceptance/**/*.mjs`,
`apps/api/migrations/**/*.py`:
- целевой размер: ≤ 12 KB;
- зона предупреждения: > 80% hard-limit;
- hard-limit: ≤ 16 KB и ≤ 350 строк.

Generated contracts, lockfiles и machine-generated artifacts не режутся искусственно по этим пределам.

Правило headroom: существующий файл в зоне >80% hard-limit можно не рефакторить в несвязанной задаче,
но новый package не должен увеличивать его дальше. Существенное расширение такой области начинается со split
или создаёт новый owner-модуль. Новый handwritten-файл сразу не должен создаваться в зоне >80%.

## 3. Бюджет контекста агента

Обязательный старт `AGENTS.md + CURRENT.md` должен оставаться ≤ 6 KB.

Block-level locator:
- сначала owner/symbol/anchor;
- начальная документация до чтения source-block ≤ 12 KB;
- source читается вокруг anchor, а не целиком;
- support/tests открываются только по необходимости.

Feature/domain route:
- `read_first` ≤ 18 KB;
- целевой `read_first` ≤ 12 KB;
- если route не укладывается, он делится на более узкие routes/blocks, а файлы переносятся в `expand_if_needed`;
- расширение route-budget запрещено как исправление CI.

Domain-specific routing preference хранится как данные map, а не как новый `if <domain>` в router-коде.
`CONTEXT_MAP` и `BLOCK_MAP` шардируются до достижения hard-limit; router и docs-validator обязаны поддерживать
shard index, а не требовать возвращения к одному гигантскому JSON.

## 4. Локальная документация

Один feature/domain имеет один короткий live ownership contract — обычно `README.md`.
Root/platform `AGENTS.md` задают правила уровня репозитория/приложения; domain `AGENTS.md` не должен повторять README.

Суммарный live Markdown непосредственно внутри feature/domain каталога — целевой ≤ 4 KB, hard ≤ 6 KB.
Подробные отчёты, старые ветки, старые команды запуска, package-history и прежние решения уходят в `docs/history/`
или `docs/reviews/`. В live local docs запрещены mutable SHA/PR/working branch/next package.

Большой предметный PRODUCT/ADMIN/UX/ARCHITECTURE/AI_RUNTIME документ допустим только как расширенный контекст
и никогда не входит в default context маленькой правки.

## 5. Scope-классы

Каждый package имеет конечный scope:
- `tiny`: до 8 файлов;
- `normal`: до 20 файлов;
- `cross_domain`: до 40 файлов и обязательные `large_scope_reason`, `domains`, `non_goals`;
- >40 файлов требует отдельного архитектурного объяснения до реализации и не является нормой.

Sensitive paths требуют явного перечисления. Автоматически повышать `max_files` после scope failure запрещено.

## 6. Review-gate по риску

Scope фиксирует `risk`: `low | medium | high`.
`high` обязателен для auth/permissions/credits/financial semantics/migrations/provider paid lifecycle/secrets/
cross-account access/release-network policy.

Для `high` package checkpoint нельзя считать технически принятым без:
1. implementer SELF_REVIEW;
2. профильных negative/race/idempotency/restart tests;
3. structured GitHub review `APPROVED`, привязанного к exact source SHA, от actor, отличного от repository owner;
4. полного required CI.

Обычный PR comment, включая `INDEPENDENT_REVIEW PASS ...`, не доказывает reviewer identity.
Если независимый GitHub actor недоступен, gate не удаляется: допускается только явный owner waiver transition.
Waiver требует owner action, exact source SHA, `independent_review=unavailable` и причину; в checkpoint хранится
как `owner_waiver=true` и не называется independent review. Неверный SHA или failed CI waiver не обходит.

`begin-next` и `begin-decided-next` проверяют source HEAD, required CI и review/waiver до создания новой ветки.
State/checkpoint пишутся только на новой ветке; ошибка записи откатывает файлы и созданную ветку.

## 7. Непрерывный audit

Каждый package перед freeze обязан выполнить maintainability delta-audit:
- список изменённых handwritten-файлов и их headroom;
- новые/изменённые block/route context bytes;
- scope size/class;
- local-doc bytes и отсутствие mutable history;
- новые owner boundaries;
- generated/lock/artifact sanity;
- self-review о том, не стала ли следующая правка дороже.

После каждых 5 завершённых продуктовых packages выполняется полный repository audit:
- top handwritten files по bytes/lines;
- top routes по initial context bytes;
- directories с наибольшим local-doc budget;
- stale/mutable docs;
- map/shard growth;
- duplicated ownership instructions;
- tools/workflows, приблизившиеся к limits.

Audit создаёт отдельный maintenance package только если выявлен долг, который нельзя безопасно закрыть в следующем
product package. Нельзя постоянно останавливать продукт ради косметического refactor; цель — предотвращать накопление долга.

## 8. Definition of Done любого будущего package

Package не получает `technical_pass`, если:
- появился giant handwritten file;
- изменённый near-limit файл вырос без split;
- route/default context превысил бюджет;
- новый feature не имеет owner route/README;
- live local docs содержат историю/ветку/старый SHA;
- scope расширен без явного основания;
- high-risk package не получил structured independent review и не имеет допустимого explicit owner waiver;
- CI стал зелёным после ослабления limit/test вместо исправления архитектуры.

## 9. MAINT-AGENT-002

Первичная нормализация должна:
1. ввести headroom/context/local-doc/workflow gates;
2. устранить текущие near-limit tests и подготовить frontend near-limit files к следующему UX package;
3. удалить stale live-документацию Accounts email и дубли domain AGENTS/README;
4. сократить обязательный root-agent context;
5. сделать router declarative и подготовить sharded maps;
6. закрепить scope classes и machine-readable high-risk review requirement;
7. зафиксировать recurring audit как часть каждого следующего package.

Лимиты этого документа считаются инженерными ограничениями проекта. Их изменение — отдельное архитектурное решение
с доказательством необходимости, а не локальный способ получить зелёный CI.

## 10. Source-First и SOURCE_AUDIT

Каждый package имеет `SOURCE_AUDIT`; глубина audit пропорциональна semantic scope. Источники проверяются в порядке:

1. действующий canonical target owner;
2. фактический target code/tests на fresh target SHA;
3. APPROVED target specs/ADR/accepted review contracts;
4. применимый donor `spikeal8-maker/IZO_ASA` на fresh donor SHA;
5. bounded external benchmark/reference, если он действительно нужен;
6. при отсутствии достаточного решения — `NEW_DECISION_REQUIRED`.

Более новый approved target contract побеждает старую target implementation gap, donor behavior, external reference и implementer proposal. Existing target code/tests исследуются до проектирования replacement; наличие нового ТЗ не разрешает переписать существующую функцию с нуля без source audit.
### SOURCE_AUDIT_MODE FULL

`FULL` обязателен при изменении observable product behavior, product/domain capability, domain/data ownership, security/auth, Credits/pricing/spend, provider semantics, storage/lifecycle, publication/privacy, major UX workflow, dedicated product surface или donor reuse.

Admin, Image, Gallery и Feed product/domain work всегда используют FULL donor audit. Он фиксирует target repo/SHA/owners/code/tests, donor repo/SHA/paths/behavior, conflicts, classifications, decisions, new decisions и resulting implementation scope.

Fresh target SHA обязателен всегда; fresh donor SHA обязателен, когда donor comparison/reuse входит в audit scope.
### SOURCE_AUDIT_MODE BOUNDED_LOCAL

`BOUNDED_LOCAL` допустим только одновременно при всех условиях: change small/local; observable semantics unchanged; domain/owner boundary unchanged; security/auth unchanged; pricing/Credits/spend unchanged; storage/persistence unchanged; donor reuse отсутствует; canonical target owner уже однозначно определяет behavior.

Audit всё равно фиксирует target SHA/owner/paths/nearest tests и explicit `OBSERVABLE_SEMANTICS_CHANGED=NO`, `OWNER_BOUNDARY_CHANGED=NO`. `DONOR_RESEARCH=NOT_REQUIRED` и `DONOR_SHA=NOT_REQUIRED` допустимы только при выполнении всех bounded-условий и записанной причине.

Если обнаружены new observable semantics, ambiguous owner, product decision или donor reuse proposal, bounded mode прекращается: перейти в FULL либо вернуть `NEW_DECISION_REQUIRED`.
### Donor classification и safety

Каждый donor item получает ровно одну classification: `ADOPT_BEHAVIOR`, `PORT_TEST`, `PORT_ASSET`, `REIMPLEMENT`, `REJECT`.

Wholesale feature copy запрещён. Donor auth/session, ledger, provider secrets, storage ownership, schema/migrations, production data/users/credentials/private runtime state и giant monolithic components не переносятся автоматически. Donor test не делает старое behavior правильным; approved target behavior побеждает.

После переноса canonical truth живёт в target repository; donor не остаётся runtime/documentation dependency.
### NEW_DECISION_REQUIRED и внешний benchmark

Implementer не выбирает новую observable semantics молча. Если target owners/code/tests, approved contracts, donor и допустимый external evidence не дают ответа, затронутая semantics получает `NEW_DECISION_REQUIRED` и не реализуется до owner/approved-contract decision. Независимые уже определённые части package могут продолжаться.

Для **существенного user-visible Chat behavior**, не полностью определённого IZO ASA sources, перед `NEW_DECISION_REQUIRED` обязателен bounded comparison **обоих current ChatGPT и current Claude**. Используются свежие проверяемые official/current product sources или проверяемая current product surface на дату package.

Benchmark record содержит date, source/reference, compared behavior, decision и reason; по применимости сравнивает clarity, interaction cost, discoverability, desktop/mobile, accessibility, recovery/persistence, safety/privacy и performance implications. Внешние продукты — research benchmark, не canonical specification. После решения authority становится IZO ASA canonical contract.
## 11. Усиленная cadence Chat и cleanup

Каждый package сохраняет Maintenance Delta из §7. Дополнительно:

- после каждых **3 завершённых Chat product packages** выполняется targeted Chat Structural Audit;
- если активная разработка Chat идёт **30 календарных дней** без трёх завершённых Chat packages, выполняется тот же targeted audit;
- правило полного repository audit после каждых **5 product packages** сохраняется;
- threshold-triggered audit выполняется раньше cadence при двух Chat production files в warning zone, scope >40, третьем temporary compatibility path одного owner, заметном test duplication/slowdown, duplicate live owner, context overflow или необходимости нарушить domain boundary.

Chat Structural Audit проверяет top Chat files/headroom, duplicate responsibilities, orphan CSS/components/hooks, stale flags/temp paths, duplicate clients/adapters, renderer/tool/file dependency growth, slow/duplicate tests, local docs/context drift и dead endpoints/contracts/types.
Temporary bridge/feature flag/dual path обязан иметь owner, reason, removal condition и acceptance gate expiry; бессрочный `TODO remove later` в accepted path запрещён. Если temp path пережил два packages после expiry, следующий package решает: удалить, formally extend с причиной или выделить maintenance package.

Garbage cleanup не удаляет accepted migrations, immutable ledger/audit/checkpoints, user Media/Artifacts, provenance reviews/history или live compatibility path без consumer proof. Test cleanup сохраняет invariant coverage.

Новая dependency допускается только для current requirement после license/maintenance/security и duplicate-framework проверки; unused dependency удаляется ближайшим safe cleanup. Flaky test чинится либо получает reproducible quarantine с owner/expiry; permanent ignore без owner запрещён.
