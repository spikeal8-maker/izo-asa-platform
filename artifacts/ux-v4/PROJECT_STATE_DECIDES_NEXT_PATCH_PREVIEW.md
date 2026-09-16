# IZO ASA — `project_state` decides-next patch preview

Статус: **staging / code-design preview**. Не применять к frozen canonical branch без отдельного lifecycle repair decision.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. Цель

Устранить deadlock, когда active package имеет `decides_next=true`, `next_package=null`, source уже frozen, а следующий package определяется только после owner acceptance.

Исправление не должно превращать `begin-next` в произвольный branch creator. Exact-head PR/workflows/review checks остаются до state mutation.

## 2. Предлагаемая CLI-модель

Сохранить текущий режим:

```text
python tools/project_state.py begin-next \
  --branch <new-branch> \
  --activate <existing-planned-next> \
  --verified-pr <current-pr>
```

Добавить owner-selected definition только для `decides_next`:

```text
python tools/project_state.py begin-next \
  --branch ux/chat-intent-reconcile \
  --activate FRONTEND-002 \
  --verified-pr 36 \
  --define-package tools/package_candidates/frontend-002.json
```

Candidate file — input текущего оператора, а не заранее committed state на frozen branch.

## 3. Candidate schema

Минимальный пример:

```json
{
  "id": "FRONTEND-002",
  "goal": "Reconcile Chat-first UX semantics without backend changes.",
  "depends_on": ["FRONTEND-001"],
  "decides_next": true
}
```

`status` из input не принимается. Tool сам создаёт package как transition candidate и сразу переводит его в `active` только после всех checks.

## 4. Изменение pure transition

Вместо безусловного:

```python
if plan.get("next_package") != activate:
    raise ValueError(...)
```

логика должна различать:

```text
1. next_package == activate
   -> existing preselected transition

2. next_package is None AND active.decides_next == true
   -> owner-selected transition
   -> activate обязан быть либо existing planned package,
      либо package definition, переданный через validated candidate input

3. everything else
   -> reject
```

## 5. Атомарность

Порядок в `begin_next` должен остаться fail-closed:

1. clean checkout;
2. current branch == working_branch;
3. source_head = exact frozen HEAD;
4. verify independent review if required;
5. fetch/validate PR evidence for exact source;
6. validate package candidate entirely in memory;
7. create new branch from exact source;
8. write `PLAN.json`, `CURRENT.md`, `CHECKPOINTS.json` on new branch;
9. rollback branch/state if write fails.

Никакая state mutation не должна происходить до шага 7.

## 6. Validation нового package

Перед branch creation отклонять candidate если:

- `id` не совпадает с `--activate`;
- `id` уже существует с неподходящим статусом;
- `depends_on` не содержит finishing active package;
- любая дополнительная dependency отсутствует или не ready;
- package пытается переопределить runtime/canonical lineage;
- поля содержат state/evidence/checkpoint/SHA/branch;
- candidate schema содержит неизвестные control fields.

Разрешённые поля лучше whitelist-ить: `id`, `goal`, `depends_on`, `decides_next`, optional bounded metadata.

## 7. Обязательные tests

Добавить к `tests/test_project_state.py` минимум:

- decides-next + null next + valid new definition → transition PASS;
- same state without `decides_next` → REJECT;
- missing direct dependency on finishing → REJECT;
- candidate id mismatch → REJECT;
- existing technical_pass id reuse → REJECT;
- malformed candidate/control fields → REJECT;
- exact-head/review failure happens before branch creation;
- write failure still restores files and deletes created branch;
- preselected `planned_next` path remains backward-compatible.

## 8. Scope recommendation

Это отдельный maintenance/process repair, не часть UX code change.

Предполагаемые owners:

- `tools/project_state.py`;
- `tools/project_state_model.py`;
- `tests/test_project_state.py`;
- `docs/DEVELOPMENT.md`;
- при необходимости schema/candidate helper.

Не менять PRODUCT/UX/runtime одновременно с lifecycle repair.

## 9. Что делать с FRONTEND-002 после repair

После того как repair сам получит свой проверенный checkpoint, следующий package definition можно активировать штатно от exact source, не создавая planning commit на frozen branch.

До этого `frontend-002-candidate-scope.json` остаётся только staging input/reference.

## 10. Self-review

PASS как patch design:

- сохраняет exact-head evidence до branch creation;
- не ослабляет independent review;
- не разрешает произвольное редактирование PLAN на frozen branch;
- сохраняет старый preselected-next flow;
- repair отделён от UX implementation.
