# SELF_REVIEW

Заполняется implementer после законченного атомарного изменения **до** объявления результата.

- Task/package:
- Base / branch / head:
- Requested `до → после`:
- Actual changed paths:
- Targeted tests executed:

## Critical review

1. **Acceptance:** исходный результат достигнут полностью? Что не достигнуто?
2. **Scope:** каждый изменённый файл необходим? Есть ли скрытая соседняя функция?
3. **Regression surface:** какие error/race/reload/restart/cancel/permission cases затронуты?
4. **Invariants:** ownership, identity, price, credits, idempotency, retries, privacy, secrets сохранены?
5. **Tests:** тесты проверяют поведение или были ослаблены ради PASS?
6. **Contracts:** нужны ли OpenAPI/migration/generated/docs updates и сделаны ли они?
7. **Context docs:** local README/context route всё ещё указывают правильный owner/test?
8. **Unknowns:** что не проверено и не должно называться готовым?

## Verdict

`PASS` / `FIX_REQUIRED` / `ESCALATE`

Короткое обоснование:

Следующее действие (одно):
