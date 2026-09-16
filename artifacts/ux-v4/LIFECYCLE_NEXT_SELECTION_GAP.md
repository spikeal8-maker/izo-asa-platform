# IZO ASA — lifecycle gap: `decides_next` + frozen head

Статус: **staging / process defect analysis**. Документ не меняет canonical branch и не является разрешением обходить `project_state.py`.

Проверено по `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. Обнаруженный разрыв

`FRONTEND-001` имеет `decides_next=true`, а `PLAN.json` содержит `next_package=null`. Это валидно по `validate_plan()`.

Одновременно `project_state.py begin-next` вызывает `transition()`, а `transition()` требует:

```python
if plan.get("next_package") != activate:
    raise ValueError(f"{activate} is not PLAN next_package")
```

Следовательно, при `next_package=null` ни один package не может быть активирован через `begin-next`.

## 2. Почему нельзя просто поправить PLAN на frozen branch

Текущий `FRONTEND-001` source head уже заморожен и exact-head CI/evidence привязаны к `5c0e79b...`.

Если после CI изменить `PLAN.json`/`CURRENT.md` на `ux/frontend-reset`, получится новый source SHA. Тогда:

- прежние required workflows больше не являются exact-head evidence;
- independent-review marker старого SHA не подходит новому SHA;
- PR merge tree меняется;
- freeze contract нарушается.

То есть ручное назначение `next_package` на frozen branch — не безопасный выход.

## 3. Второй разрыв: новый package отсутствует в PLAN

Даже если разрешить `decides_next` активировать package при `next_package=null`, кандидат `FRONTEND-002` сейчас не существует в `PLAN.json`.

`dependency_problems()` возвращает `unknown package`, если `activate` отсутствует.

Поэтому для действительно нового owner-selected package требуется атомарно решить две задачи **уже на новой ветке**:

1. добавить package definition;
2. активировать его от проверенного frozen source.

## 4. Требуемое свойство исправления

Безопасный lifecycle должен сохранять правило:

> frozen source сначала полностью проверяется как источник следующей ветки; state mutation происходит только после создания новой ветки от этого exact head.

Нельзя делать отдельный planning commit на frozen branch только для выбора следующего package.

## 5. Предлагаемый direction

`begin-next` должен поддерживать два режима:

### A. Preselected next

Текущее поведение сохраняется: `next_package=<existing planned_next>` → activate exactly that package.

### B. `decides_next` selection

Если:

- current active package имеет `decides_next=true`;
- `next_package is null`;
- exact source/PR/workflows/review evidence прошли;

то `begin-next` может на **новой ветке** принять package definition и активировать его атомарно.

Минимальные обязательные поля нового package:

- id;
- goal;
- depends_on, обязательно включая finishing package;
- optional `decides_next`;
- initial status internally treated as `planned_next` only inside the transition.

## 6. Fail-closed требования

Исправление обязано отклонять:

- новый package без прямой зависимости от finishing package;
- существующий completed/active package под видом нового;
- выбор нового package, если active package не `decides_next`;
- branch creation до проверки exact-head PR/workflows/independent review;
- partial state write без rollback;
- изменение frozen source branch.

## 7. Почему это блокирует реальный FRONTEND-002

Даже после owner visual acceptance и independent review текущая команда `begin-next --activate FRONTEND-002` завершится ошибкой: package не является `PLAN next_package` и вообще отсутствует в `packages`.

Поэтому подготовленный UX v4 scope сейчас **не может быть штатно активирован** существующим CLI.

Это не UX-дефект и не причина вручную обходить lifecycle; это отдельный continuation-safety gap в project-state tooling.

## 8. Временное правило

До исправления:

- не менять `ux/frontend-reset`;
- не создавать canonical next branch вручную;
- не выдавать staging branch за package transition;
- продолжать только анализ/patch preview в `docs/ux-spec-v4-staging`.

## 9. Self-review

PASS как process analysis:

- вывод следует непосредственно из `PLAN.json`, `project_state.py` и `project_state_model.py`;
- не предлагается ослаблять exact-head evidence;
- не предлагается пропускать independent review;
- не предлагается мутировать frozen branch;
- blocker отделён от UX implementation scope.
