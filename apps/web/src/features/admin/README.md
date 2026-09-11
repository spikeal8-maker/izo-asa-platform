# Web Admin · локальная карта

Этот feature отображает server-authorized staff operations. Наличие ссылки/route не даёт permission.

| Видимый блок / задача | Основной файл | Ближайший test |
|---|---|---|
| Admin route/list/detail shell | `AdminPage.tsx` | `e2e/admin.spec.ts` |
| Начисление/компенсация | `GrantForm.tsx` | `e2e/admin.spec.ts` |
| Общий transport/CSRF | `../../shared/workspace-api.ts` | affected admin spec |

## Инварианты

- backend проверяет permission/scope/ownership на каждой операции;
- UI hint о роли не считается авторизацией;
- amount/reason/case semantics не вычисляются альтернативным client ledger;
- неизвестный mutation outcome не повторяется с новым operation ID;
- raw provider secrets не должны появляться в generic admin form.

Для локального текста/layout не читать весь `docs/ADMIN.md`. Если меняется permission, grant command,
settings/catalog semantics — перейти в `api.admin` и только затем открыть соответствующий раздел ADMIN.
