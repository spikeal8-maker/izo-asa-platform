# Web Admin · локальная карта

Этот feature отображает server-authorized staff operations. Наличие ссылки/route не даёт permission.

| Видимый блок / задача | Основной файл | Ближайший test |
|---|---|---|
| Admin loading/search/audit orchestration | `AdminPage.tsx` | `e2e/admin.spec.ts` |
| Users/detail/audit presentation | `AdminPanels.tsx` | `e2e/admin.spec.ts` |
| Начисление/компенсация | `GrantForm.tsx` | `e2e/admin.spec.ts` |
| ACCESS load/mutate orchestration | `AccessPage.tsx` | `e2e/access.spec.ts` |
| ACCESS lookup/subject presentation | `AccessPanels.tsx` | `e2e/access.spec.ts` |
| Общий transport/CSRF | `../../shared/api.ts` | affected admin/access spec |

## Инварианты

- backend проверяет permission/scope/ownership на каждой операции;
- UI hint о роли не считается авторизацией;
- access-only сотруднику не показываются unrelated Users/Audit links;
- ACCESS mutation использует только server allowlist, `scope=global`, finite TTL и fresh password;
- неизвестный mutation outcome повторяется с тем же operation ID; при изменении payload создаётся новый ID;
- password очищается после каждой попытки и не хранится в receipt/local storage;
- raw provider secrets не должны появляться в generic admin form.

Для локального текста/layout открывать соответствующий panel-owner, а не весь feature. Если меняется permission,
delegation ceiling, settings/catalog semantics — перейти в `api.access`/`api.admin` и только затем открыть ADMIN.
