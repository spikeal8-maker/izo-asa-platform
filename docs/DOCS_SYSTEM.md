# Система документации IZO ASA

Цель — минимальный достаточный контекст для безопасного изменения проекта человеком или coding-агентом.
Один факт имеет одного владельца; история не подмешивается в live context.

## 1. Уровни контекста

1. `AGENTS.md` — короткие долговечные правила.
2. `CURRENT.md` + `PLAN.json` — текущий package, base, branch, dependency graph.
3. `BLOCK_MAP.json` → точный UI/API block; `CONTEXT_MAP.json` → fallback route.
4. Local README/AGENTS и затем предметные specs — только при конкретной зависимости.
5. `CHECKPOINTS.json`, `reviews/`, `history/` — provenance/history; не default context.

## 2. Владельцы фактов

| Факт | Владелец |
|---|---|
| Current package/base/branch/dependencies | `PLAN.json` |
| Immutable CI evidence | `CHECKPOINTS.json` |
| Короткое текущее состояние | `CURRENT.md` |
| Block owner/symbol/anchor/test | `BLOCK_MAP.json` |
| Feature/domain fallback | `CONTEXT_MAP.json` |
| Coding-agent process / SELF_REVIEW | `DEVELOPMENT.md` |
| File/context/scope budgets и recurring audit | `MAINTAINABILITY.md` |
| Пользовательское поведение | `PRODUCT.md` |
| Admin/permissions/settings | `ADMIN.md` |
| Visual/responsive/accessibility | `UX.md` |
| Domain/data boundaries | `ARCHITECTURE.md` |
| Provider/runtime/credentials | `AI_RUNTIME.md` |
| Architecture decisions | `adr/ADR-*.md` |
| Docker/release/network/backup | `OPERATIONS.md` |
| Доказанные факты | `STATUS.md` |
| Package report | `reviews/<ID>.md` |

## 3. Progressive disclosure

Порядок:
`AGENTS → CURRENT/verify → block locator → surrounding source block/test`.
Если block неизвестен: `route → local README → owner source/test`.

Большой предметный документ открывается только по зависимости. Lockfiles, generated contracts, CHECKPOINTS,
history и соседние feature по умолчанию закрыты. Бюджеты initial context обязательны по `MAINTAINABILITY.md`.

## 4. Local ownership contract

Самостоятельный feature/domain имеет короткий README:
- routes/visible blocks/commands;
- owner files;
- внешние зависимости;
- invariants;
- nearest tests;
- когда расширять контекст.

README не является журналом. Domain-local Markdown считается единым live-context budget: подробная история, старые ветки,
старые команды и package evidence уходят из каталога кода в `history/`/`reviews/`.

## 5. Plan/checkpoints/freeze

`PLAN.json` различает runtime base, current-package base и working branch.
PLAN хранит короткие checkpoint refs; evidence находится в CHECKPOINTS.

После required CI working head замораживается без status commit. PR evidence помечается `pr_merge_tree`, если проверен
synthetic merge. `project_state.py begin-next` проверяет evidence/dependencies, создаёт следующую ветку от frozen source,
записывает checkpoint и переводит package state уже в новой ветке.

## 6. Definition of Done документации

1. `tools/check_docs.py` проходит.
2. Block/route ведёт к существующему owner/anchor/test.
3. Новый domain имеет local README + route; ключевые операции имеют block ID.
4. Local live docs укладываются в aggregate budget и не содержат mutable history.
5. Route/block initial context укладывается в budget.
6. PLAN/CURRENT меняются только на новой ветке при state transition.
7. CI evidence находится в CHECKPOINTS.
8. STATUS содержит только доказанные факты.
9. Stable docs не содержат mutable SHA/PR.
10. Maintainability delta проверен.

## 7. Запрещено

- Второй MASTER_PLAN/ROADMAP/NOW.
- Current SHA/PR/next package в stable/local docs.
- CI history внутри PLAN.
- Broad spec как default context маленькой правки.
- Повышение file/context/scope limit после failure вместо разделения ответственности.
- Дублирование одного ownership rule в README и domain AGENTS.
- Documentation-only изменение как скрытый runtime/security change.

## 8. Автоматические предохранители

`context.py` ищет block до route и fail-closed на ambiguity.
`project_state.py` охраняет lineage/checkpoints.
`check_docs.py` проверяет PLAN/CURRENT/checkpoints, owner/anchor/routes, coverage, UTF-8, stable docs,
aggregate local-doc budgets и initial context budgets.
Architecture guard проверяет handwritten production/tests/tools/e2e/acceptance/migrations, headroom и workflow size.

`CONTEXT_MAP`/`BLOCK_MAP` должны быть шардированы до достижения hard-limit; router не должен становиться местом
domain-specific `if guest/chat/video/...` логики. Routing signals по возможности declarative.

Численные пределы и audit cadence принадлежат `MAINTAINABILITY.md`.
