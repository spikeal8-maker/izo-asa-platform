# Web Credits · локальная карта

Страница баланса — read surface общего server Credits ledger. Она не рассчитывает authoritative balance сама.

| Видимый блок / задача | Основной файл | Ближайший test |
|---|---|---|
| Баланс/история | `CreditsPage.tsx` | `e2e/accounts.spec.ts` |
| Общий credits transport | `../../shared/workspace-api.ts` | affected web spec |

## Инварианты

- available/reserved/history приходят с backend;
- UI не делает локальный settle/refund после job cancel/error;
- product Credits не смешиваются с provider USD/microUSD cost;
- форматирование суммы не меняет server semantics.

Для изменения reserve/settle/release перейти в `api.credits`; для тарифного доступа — в `api.entitlements`.
