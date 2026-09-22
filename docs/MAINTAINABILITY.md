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
