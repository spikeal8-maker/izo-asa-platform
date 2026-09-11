# Web · правила точечных изменений

Наследует корневой `AGENTS.md`. Сначала выбери route через `python tools/context.py`; для feature читай его
локальный README, component/CSS и ближайший E2E. Не открывай весь backend или PRODUCT ради кнопки.

| Область | Локальная карта | Основной test |
|---|---|---|
| Shell/navigation/theme | `src/shell/App.tsx`, `layout.css`, `theme.css` | `e2e/shell.spec.ts` |
| Studio/result/provider selection | `src/features/studio/README.md` | `e2e/studio.spec.ts`, `provider.spec.ts` |
| Gallery/private asset UI | `src/features/gallery/README.md` | `e2e/gallery.spec.ts` |
| Account/security | `src/features/accounts/README.md` | `e2e/accounts.spec.ts`, `email-security.spec.ts` |
| Admin | `src/features/admin/README.md` | `e2e/admin.spec.ts` |
| Credits | `src/features/credits/README.md` | affected account/studio spec |
| Общий session/API transport | `src/shared/workspace.tsx`, `api.ts`, `workspace-api.ts` | все реально зависимые specs |

## Web invariants

Backend владеет identity, permissions, price, Credits, provider config, Job state и Media ownership. UI не создаёт
fallback-wallet/gallery/success. Unknown mutation response сохраняет тот же operation ID до server evidence.
Private data effect имеет abort/cleanup; Object URL освобождается. 401 очищает private state.

Studio/Gallery/Accounts/Admin — sibling features; feature не импортирует внутренности соседа. Общие primitives идут
через `shared/`. Неподдержанная server action не изображается работающей кнопкой.

Для локальной UI-правки: `npm run build` + affected spec на нужных viewport. Общий transport требует зависимых specs.
Полная viewport matrix/CI перед технической приёмкой сохраняется. После изменения обязателен SELF_REVIEW.
