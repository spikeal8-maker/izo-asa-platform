# Web · точечные изменения

Наследует корневой AGENTS. Реальная identity, цена, лимиты, задания и баланс принадлежат backend.

| Что меняется | Читать сначала | Ближайшая проверка |
|---|---|---|
| Навигация и общая тема | src/shell/App.tsx, layout.css, theme.css | shell.spec.ts |
| Студия, quote, подтверждение | features/studio/Studio.tsx, studio/README.md | studio.spec.ts |
| Повтор потерянного submit | shared/submission.ts, Studio.tsx | lost response / damaged storage |
| Список/карточка задания, отмена | studio/ResultPanel.tsx, shared/workspace.tsx | studio.spec.ts |
| Список работ и просмотр | gallery/Gallery.tsx, AssetPage.tsx, PrivateImage.tsx | gallery.spec.ts |
| Сессия/общий transport | shared/workspace.tsx, api.ts, workspace-api.ts | все затронутые account/admin/studio/gallery specs |
| Телефон/QHD/4K | CSS затронутой области | тот же spec с нужным viewport |

Начать с компонента и ближайшего теста; не читать всю админку, старую IZO_ASA или весь generated API ради кнопки. В UI нет отдельного кошелька, fallback-галереи или provider SDK. Прототип удалён; не возвращать DemoState, имитацию успешной генерации и локальное списание.

Профильный цикл: `npm run build`, затем `npx playwright test e2e/studio.spec.ts --project=phone --project=laptop` для студии. Gallery — свой spec. Общий transport требует всех зависимых экранов. npm ci только для нового checkout или изменённого lock/runtime. Полный CI и 10 viewport перед приёмкой сохраняются; тесты реального PostgreSQL/S3 отдельно от mocked viewport.

У каждого эффекта с частными данными — abort/cleanup; Object URL освобождается. Номер незавершённого submit привязан к account, содержит только IDs. Не менять operation ID после сетевого сбоя. Цена берётся только из quote. Ошибка auth/хранилища не превращается в успешный локальный результат.

Studio и Gallery — соседние features; не импортировать их друг из друга. shared/ui не знает features. Новые API-клиенты используют общий transport. Неподдержанные delete/publish/input-reference не изображать работающими кнопками.

`Review Source` выдаёт проверяемый архив tracked source с tree/blob manifest. Это не архив .git/окружения и не доказательство прохождения тестов; сравнить tree с точным SHA PR. Приватные runtime fixtures/пароли и содержимое RUNNER_TEMP в артефакты не добавлять.
