# Web · точечные изменения

Наследует корневой AGENTS. Код UI не предоставляет серверные права.

| Что меняется | Где искать сначала | Ближайшая проверка |
|---|---|---|
| Навигация/тема/общая раскладка | src/shell/App.tsx, layout.css, theme.css | shell.spec.ts, phone+laptop |
| Форма/параметры/цена макета | src/features/studio/Studio.tsx | studio.spec.ts, phone+laptop |
| Состояние результата | src/features/studio/ResultPanel.tsx | studio.spec.ts |
| Список/просмотр работ | src/features/gallery/Gallery.tsx, AssetPage.tsx | gallery.spec.ts |
| Демо-состояние | src/features/prototype/DemoState.tsx, demo.ts | studio+gallery, refresh/cancel/error |
| Общий dialog/icon | src/shared/ui | shell+studio+gallery, focus/keyboard |
| Широкий экран | styles затронутой области | тот же spec: qhd/uhd/hidpi-150/hidpi-200 |

Использовать уже установленные зависимости, npm ci только для нового checkout/изменённого lock/runtime. Для UI не запускать Docker, не читать backend и старый проект без конкретной зависимости.

После кода: `npm run build`, затем `npx playwright test e2e/studio.spec.ts --project=phone --project=laptop` (заменить только имя действительно затронутого spec). Общий компонент требует всех зависимых specs; расширенная матрица и полный CI перед приёмкой не отменяются. Playwright-профиль не доказывает реальную ОС/SDK.

Shell знает маршруты, shared/ui не знает features, studio/gallery используют общий demo-state только в прототипе. Не импортировать studio из gallery или наоборот. src/features/prototype — явно fake adapter, не место будущей авторизации/ledger. Реальный API вводится отдельным этапом, не скрытой заменой demo на paid call.

Сначала читать нужный компонент и его test; не весь CSS и docs/ADMIN для кнопки. Новые стили локализованы областью, общие tokens — theme.css. Не сжимать строки и не переносить случайные куски ради лимита. Никаких новых пакетов или глобального transform:scale ради вёрстки.
