# Web Accounts · локальная карта

Используется для `/login`, `/register`, `/account` и security routes. Backend остаётся владельцем identity,
session, password/recovery policy и permissions; UI не доказывает права сам.

| Видимый блок / задача | Основной файл | Ближайший test |
|---|---|---|
| Вход/регистрация/карточка аккаунта | `AccountPage.tsx` | `e2e/accounts.spec.ts` |
| Сессии/security/recovery screens | `SecurityPage.tsx` | `e2e/accounts.spec.ts`, `e2e/email-security.spec.ts` |
| Локальный внешний вид | `accounts.css` | тот же affected spec |
| Общий auth/session transport | `../../shared/workspace.tsx`, `../../shared/api.ts` | affected account + dependent specs |

## Инварианты

- client role/user ID не создают identity или permission;
- пароль/proof/session token не сохраняются в UI state дольше необходимого и не попадают в URL/log;
- 401/403 очищают private state, а не превращаются в guest success;
- UI не изобретает recovery/session semantics — при их изменении перейти в `api.accounts` context route.

Для текста, отступа или кнопки не читать весь backend. Для изменения auth semantics — расширить контекст через
`python tools/context.py --key api.accounts`.
