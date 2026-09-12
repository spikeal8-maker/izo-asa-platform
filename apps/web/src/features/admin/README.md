# Web Admin · локальная карта

Этот feature отображает server-authorized staff operations. Наличие ссылки/route не даёт permission.

| Видимый блок / задача | Основной файл | Ближайший test |
|---|---|---|
| Admin route/list/detail shell | `AdminPage.tsx` | `e2e/admin.spec.ts` |
| Начисление/компенсация | `GrantForm.tsx` | `e2e/admin.spec.ts` |
| A-28 доступ персонала | `AccessPage.tsx` | `e2e/access.spec.ts` |
| Общий transport/CSRF | `../../shared/api.ts` | affected admin/access spec |

## Инварианты

- backend проверяет permission/scope/ownership на каждой операции;
- UI hint о роли не считается авторизацией;
- access-only сотруднику не показываются unrelated Users/Audit links;
- ACCESS mutation использует только server allowlist, `scope=global`, finite TTL и fresh password;
- неизвестный mutation outcome повторяется с тем же operation ID; при изменении payload создаётся новый ID;
- password очищается после каждой попытки и не хранится в receipt/local storage;
- raw provider secrets не должны появляться в generic admin form.

Для локального текста/layout не читать весь `docs/ADMIN.md`. Если меняется permission, delegation ceiling,
settings/catalog semantics — перейти в `api.access`/`api.admin` и только затем открыть соответствующий раздел ADMIN.
