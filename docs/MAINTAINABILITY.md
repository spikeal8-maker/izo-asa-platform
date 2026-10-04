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

Обязательный старт `AGENTS.md + CURRENT.md`: target ≤ 4.5 KB, hard ≤ 6 KB.
Live `PLAN.json`: target ≤ 4 KB, warning > 5 KB, hard < 6 KB. Исторический package registry не входит в default context:
для конкретного package используется bounded query `project_state.py show-package <ID>`, а не чтение всего `PACKAGES.json`.

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

Risk определяется **семантикой и trust boundary**, а не количеством файлов. `cross_domain`, API+web diff, generated contract
или большой bounded scope сами по себе не являются причиной `risk=high`. Обычные Chat history/scroll/renderer/actions,
не затрагивающие перечисленные sensitive boundaries, по умолчанию классифицируются low/medium. Искусственное повышение
risk ради дополнительного owner/review gate запрещено так же, как его искусственное понижение ради обхода gate.

Для `high` package checkpoint нельзя считать технически принятым без:
1. implementer SELF_REVIEW;
2. профильных negative/race/idempotency/restart tests;
3. structured GitHub review `APPROVED`, привязанного к exact source SHA, от actor, отличного от repository owner;
4. полного required CI.

Обычный PR comment, включая `INDEPENDENT_REVIEW PASS ...`, не доказывает reviewer identity.
Единственное историческое исключение `legacy_pr252_review` принимает owner-authenticated pre-merge comment как
legacy closeout evidence для строго зафиксированных там PR head и merge commit; это не правило для иных PR и не waiver.
Если независимый GitHub actor недоступен, gate не удаляется: допускается только явный owner waiver transition.
Waiver требует owner action, exact source SHA, `independent_review=unavailable` и причину; в checkpoint хранится
как `owner_waiver=true` и не называется independent review. Неверный SHA или failed CI waiver не обходит.

Повторный human review не требуется для machine-proven **mechanical state-only closeout**, определённого в
`DEVELOPMENT.md`: такой closeout не пересматривает product diff и обязан fail-closed при любом выходе за state/checkpoint
allowlist. Это исключение не распространяется на runtime/test/schema/security изменения.

`begin-next` и `begin-decided-next` проверяют source HEAD, required CI и review/waiver до создания новой ветки.
State/checkpoint пишутся только на новой ветке; ошибка записи откатывает файлы и созданную ветку.

## 7. Итерационный structural audit

Структурный cleanup привязан к принятым итерациям, а не к календарю:

- **EVERY PACKAGE** — перед freeze выполняется Maintenance Delta: changed handwritten headroom, context-route delta, scope, local-doc/state leakage, owner/dependency/temp-path delta и self-review стоимости следующей правки;
- **EVERY 3 ACCEPTED PRODUCT PACKAGES** — targeted structural audit соответствующего активно развиваемого product/domain;
- **EVERY 5 ACCEPTED PRODUCT PACKAGES** — full repository agent-economy audit: top handwritten owners/routes/docs, state/context growth, duplicate ownership, stale/temp paths, test/tool/workflow pressure.

Audit запускается раньше cadence, если evidence показывает хотя бы одно:
- live/default agent context >75% hard budget;
- affected context route >75% hard budget;
- changed handwritten owner входит в >80% warning zone либо near-limit owner требует дальнейшего роста;
- duplicate live owner;
- scope >40;
- повторяющиеся temporary compatibility paths;
- meaningful test duplication/slowdown;
- state/history начинает попадать в default context.

Hard-limit блокирует acceptance. Warning/threshold запускает анализ, но сам по себе не блокирует несвязанную product work.

Findings классифицируются:
- **COSMETIC** — не останавливает product development;
- **LOCAL_DEBT** — закрывается в ближайшем подходящем product package;
- **STRUCTURAL_BLOCKER** — bounded maintenance package до дальнейшего роста затронутой области.

Но дефект, уже видимый в текущем candidate и нарушающий canonical UX/acceptance его package, нельзя понижать до
`LOCAL_DEBT` только чтобы показать preview владельцу. Такой finding исправляет bot-to-bot loop до visual acceptance.
Владелец не является первым visual regression detector.

Audit не создаёт maintenance package автоматически. Цель — устранить structural blocker до дальнейшего роста, а не регулярно останавливать продукт ради косметического refactor.

## 8. Definition of Done любого будущего package

Package не получает `technical_pass`, если:
- появился giant handwritten file;
- изменённый near-limit файл вырос без split;
- route/default context превысил бюджет;
- новый feature не имеет owner route/README;
- live local docs содержат историю/ветку/старый SHA;
- scope расширен без явного основания;
- high-risk package не получил structured independent review и не имеет допустимого explicit owner waiver;
- user-visible candidate не прошёл обязательный browser/visual review по `DEVELOPMENT.md`;
- owner preview не привязан к exact source/build provenance;
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
## 11. Cleanup и freshness

Structural cadence полностью определяется accepted-package counters и threshold evidence из §7; календарного structural trigger нет.

Calendar-based freshness допустима отдельно только для security/dependency monitoring, когда возраст advisory, dependency или upstream policy сам является предметом риска. Такая проверка не подменяет structural audit и не создаёт refactor package по времени.

Targeted product/domain audit проверяет top owner files/headroom, duplicate responsibilities, stale flags/temp paths, duplicate clients/adapters, dependency growth, slow/duplicate tests, local docs/context drift и dead contracts.

Temporary bridge/feature flag/dual path обязан иметь owner, reason, removal condition и acceptance gate expiry; бессрочный `TODO remove later` в accepted path запрещён. Если temp path пережил два packages после expiry, следующий подходящий package обязан решить: удалить, formally extend с причиной либо классифицировать долг по §7.

Garbage cleanup не удаляет accepted migrations, immutable ledger/audit/checkpoints, user Media/Artifacts, provenance reviews/history или live compatibility path без consumer proof. Test cleanup сохраняет invariant coverage.

Merged same-repository head branches считаются ephemeral: после merge и после того, как ветка перестала быть live state reference, cleanup-workflow удаляет её автоматически; provenance остаётся в PR, merge commit и checkpoint. Default branch, protected branches, open-PR heads и ветки из canonical `working_branch`/`runtime_base`/`current_package_base` не удаляются.

Dependabot остаётся включённым, но routine version updates группируются по ecosystem и имеют небольшой open-PR limit, чтобы dependency maintenance не создавал десятки параллельных веток. Security remediation не отключается ради уменьшения количества PR; security finding может быть выделен в отдельный bounded package.

Новая dependency допускается только для current requirement после license/maintenance/security и duplicate-framework проверки; unused dependency удаляется ближайшим safe cleanup. Flaky test чинится либо получает reproducible quarantine с owner/expiry; permanent ignore без owner запрещён.
