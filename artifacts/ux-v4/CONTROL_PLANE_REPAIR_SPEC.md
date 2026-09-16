# IZO ASA — control-plane repair specification

Статус: **staging maintenance specification / не active package**.

Этот документ объединяет найденный lifecycle defect #188, требования к безопасному исправлению `project_state` и усиление independent-review identity. Он не разрешает вручную менять frozen `FRONTEND-001`.

Source under protection: `ux/frontend-reset@5c0e79b6fc3a7120207d0889b176fbfed3dab973`, PR #36.

---

## 1. Problem A — `decides_next + next_package=null` deadlock

Текущее состояние валидируется, если active package имеет `decides_next=true` и `next_package=null`.

Но `transition()` требует:

```python
if plan.get("next_package") != activate:
    raise ValueError(...)
```

Поэтому ни один новый package не может быть активирован через штатный `begin-next`.

Дополнительная проблема: новый owner-selected package может ещё отсутствовать в `PLAN.packages`, а текущий `dependency_problems()` считает его unknown.

Это реальный control-plane defect, а не UX issue.

---

## 2. Repair goal

Штатный tool должен поддерживать два режима без ослабления freeze/evidence:

### Mode A — preselected next

Текущее поведение сохраняется:

- `PLAN.next_package=<existing planned_next>`;
- `--activate` обязан совпадать;
- dependencies проверяются;
- branch создаётся от exact frozen source.

### Mode B — owner-selected next for `decides_next`

Разрешается только если одновременно:

- current active package имеет `decides_next=true`;
- `next_package is null`;
- exact source clean/frozen;
- independent review requirement закрыт;
- PR + required workflows + merge-tree evidence валидны;
- new package definition валидирована **полностью в памяти до branch creation**.

После этого новая ветка создаётся строго от frozen source и только на ней записываются PLAN/CURRENT/CHECKPOINTS.

---

## 3. Candidate package input

Предлагаемый CLI:

```text
python tools/project_state.py begin-next \
  --branch <new-branch> \
  --activate <PACKAGE-ID> \
  --verified-pr <PR> \
  --define-package <candidate.json>
```

`--define-package` допустим только для Mode B.

Минимальная schema:

```json
{
  "id": "FRONTEND-002",
  "goal": "Reconcile Chat-first UX semantics without backend changes.",
  "depends_on": ["FRONTEND-001"],
  "decides_next": true
}
```

Input не имеет права задавать:

- `status`;
- checkpoint/evidence/SHA;
- branch/canonical lineage/runtime base;
- arbitrary control fields.

Разрешённые поля должны быть whitelist-ированы.

---

## 4. Validation order — fail closed

`begin_next` обязан выполнять порядок:

1. load/validate current PLAN;
2. clean checkout;
3. current branch == PLAN working_branch;
4. source_head = exact current HEAD;
5. load current active scope;
6. если high-risk — validate independent review for exact source;
7. fetch/validate PR evidence and required workflows for exact source;
8. parse candidate (если Mode B);
9. validate candidate entirely in memory;
10. compute updated PLAN/checkpoint in memory;
11. reject if new branch name invalid/equal/current/already conflicting;
12. `git switch -c <branch> <source_head>`;
13. write PLAN/CURRENT/CHECKPOINTS;
14. on any write failure restore originals, switch back, delete new branch;
15. print exact evidence/source transition.

До шага 12 запрещена state mutation frozen branch.

---

## 5. Candidate validation rules

Reject если:

- active package не `decides_next`, а candidate пытается заменить null next;
- candidate `id != --activate`;
- id пустой/не соответствует package naming convention;
- id уже используется active/technical_pass/historical package;
- `depends_on` не содержит finishing package напрямую;
- extra dependency отсутствует или не ready;
- goal пустой/не string/не bounded;
- candidate пытается задать state/evidence/lineage/branch/SHA;
- unknown fields не входят в whitelist;
- current `next_package` уже preselected и candidate пытается его обойти.

Existing planned package может быть выбран из null-next только если его status/dependencies допустимы и active package действительно `decides_next`; это поведение должно быть явно протестировано.

---

## 6. Pure model changes

Предпочтительная архитектура: сохранить `transition()` строгим для уже-normalized PLAN и добавить отдельный pure helper, например:

```text
prepare_activation(plan, activate, candidate?) -> normalized_plan
```

Helper:

- различает Mode A/Mode B;
- добавляет validated new package только in-memory;
- временно формирует допустимый `planned_next` state;
- затем вызывает существующий строгий `transition()`.

Это лучше, чем превращать `transition()` в большую ветвящуюся функцию с необязательными security bypass paths.

---

## 7. Required tests

### Pure model

- preselected next continues to pass;
- decides-next + null next + valid new candidate passes;
- decides-next + null next + valid existing eligible package passes if supported by final design;
- active not decides_next -> reject;
- candidate id mismatch -> reject;
- reused completed/active package id -> reject;
- missing direct finishing dependency -> reject;
- unready extra dependency -> reject;
- malformed/unknown control fields -> reject;
- candidate cannot inject status/checkpoint/evidence/lineage.

### Orchestration

- independent-review failure occurs before any branch creation;
- PR/workflow/merge-tree failure occurs before any branch creation;
- candidate validation failure occurs before any branch creation;
- successful path creates branch from exact source head;
- PLAN/CURRENT/CHECKPOINTS are written only after branch creation;
- write failure restores all original files and deletes created branch;
- checkpoint evidence remains bound to finishing exact source.

### CLI

- existing syntax remains backward compatible;
- `--define-package` rejected outside valid decides-next state;
- missing candidate rejected when new id absent from PLAN;
- output names active package/new branch/source SHA without exposing secrets.

---

## 8. Problem B — independent-review identity weakness

Текущий review gate защищает exact SHA, но строка вида:

```text
INDEPENDENT_REVIEW PASS source=<sha> reviewer=<id>
```

сама по себе не доказывает, что:

- comment author == declared reviewer;
- reviewer отличается от implementer;
- reviewer разрешён policy;
- был реальный GitHub review approval.

### Required hardening

Для high-risk package минимум:

1. получить structured PR review/comment author identity через GitHub API;
2. exact source SHA остаётся обязательным;
3. `reviewer` должен соответствовать фактическому actor либо marker вообще убрать в пользу structured review;
4. actor не должен совпадать с implementer/committer, если policy требует independence;
5. предпочтительно требовать GitHub review state `APPROVED` на exact commit/head и дополнительно machine-readable review evidence;
6. stale approval старого SHA не переносится на новый source;
7. self-review никогда не удовлетворяет independent gate.

Конкретная reviewer allowlist/team policy — отдельное repository governance решение; tool должен иметь fail-closed interface для неё, а не hard-code произвольный username.

---

## 9. Break-glass recovery

Поскольку control-plane может сломать собственный `begin-next`, нужен заранее определённый recovery path.

Он используется только для ремонта lifecycle tooling и требует:

- explicit owner approval;
- exact frozen source SHA;
- доказанные required CI + independent review finishing package;
- отдельный maintenance scope;
- branch строго от exact source;
- никаких product/runtime изменений;
- audit trail в issue/review report;
- после ремонта — возврат к обычному `project_state` и запрет использовать recovery как нормальный workflow.

Break-glass не должен быть `--force` флагом в обычном tool. Это отдельная аварийная процедура.

---

## 10. Scope maintenance package

Рекомендуемый package: `MAINT-LIFECYCLE-001`.

Primary files:

- `tools/project_state_model.py`;
- `tools/project_state.py`;
- `tools/review_evidence.py` (если identity hardening входит в тот же пакет);
- `tests/test_project_state.py`;
- отдельные review-evidence tests при необходимости.

Docs only if contract реально меняется:

- `docs/DEVELOPMENT.md`;
- `docs/MAINTAINABILITY.md` для structured reviewer identity/break-glass rule.

Не входят PRODUCT/UX/frontend/backend business files.

Risk: **high**, потому что package управляет lineage/review gates.

---

## 11. Acceptance

Repair принят только если:

- old preselected-next flow green;
- null-next decides-next flow green;
- evidence/review/candidate failures happen before branch creation;
- no frozen source mutation;
- rollback proven;
- independent-review identity cannot be self-asserted простой строкой;
- tests fail if actor/SHA/review state не удовлетворяют policy;
- full required CI green на exact repair head;
- independent review самого maintenance package присутствует.

Главный принцип: **control-plane repair не имеет права ослаблять control-plane ради собственного прохождения.**
