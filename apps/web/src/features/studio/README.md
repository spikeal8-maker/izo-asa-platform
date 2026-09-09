# IMAGE-001 · серверное рабочее пространство

U-09/U-10 — Studio; U-17/U-18 — ResultPanel (list/detail jobs); U-19/U-20 — Gallery/AssetPage.
Один серверный Account/Credits/Jobs/Media. Реальный AI не подключён: только test.image.v1,
диагностический PNG и тестовые баллы. Функция backend выключена по умолчанию.

## Контракт

Studio читает auth/me, entitlements и credits. Доступные размеры — пересечение policy
и текущего test-контракта32…512px. Quote содержит серверные prompt/размер/цену/expiry;
submit после явного подтверждения отправляет только quote_id/operation_id с CSRF.
Параметры owner/цены/key/executor не передаются клиентом.

До отправки IDs сохраняются в sessionStorage под account-specific key. Пароли, CSRF,
prompt, баланс и bytes там не хранятся. Потерянный ответ и refresh не меняют operation ID;
повтор только по действию пользователя. Неподтверждённый исход не делает новый job.
Сбой записи или повреждённый pending record блокирует submit. Известный отказ до
admission позволяет запросить новую quote; неизвестная ошибка сохраняет старый ID.
Это не обещание exactly-once внешнего провайдера и не постоянное межустройственное хранилище черновика.

Задания читаются последовательно каждые2s, без параллельных poll; terminal/error/
reconciliation_required останавливают автоматический опрос. Отмена использует серверную
команду и не изменяет UI-баланс самостоятельно. Время progress не придумывается.

Gallery читает только собственную страницу metadata. Поиск локален текущей странице,
не объявлен глобальным. До открытия работы оригиналы не загружаются. Thumbnail pipeline
не добавлен. Detail получает session-bound ticket120s и проверяет PNG MIME/размер/hash.
Object URL живёт до unmount/смены сессии. Download каждый раз получает новую серверную
ссылку, не отдаёт ранее закешированный preview blob. Истёкшая/отозванная сессия не даёт
новых файлов. Уже скачанные человеком копии отозвать нельзя.

WorkspaceGate перепроверяет сессию при возврате на вкладку и очищает private UI при401;
запросы предыдущей страницы отменяются. Серверные guards остаются обязательными.

## Что не реализовано

Нет генерации нейросетью, input references, публикации/удаления asset, thumbnails,
сохранения prompt draft между входами, webhook-доставки или production hardening.
Старый browser DemoState, fake ledger и SVG-результат удалены; их tests заменены
проверками реального протокола. Исторические прототипы остаются в Git, не в runtime.

## Проверки

`npm run build`; `npx playwright test e2e/studio.spec.ts e2e/gallery.spec.ts --project=phone --project=laptop`.
Подставные API fixtures явно находятся в e2e/workspace-fixtures.ts; они не подтверждают backend.
Настоящий путь — tools/image_acceptance.py и acceptance/image-live.mjs в изолированном CI:
browser grant → login → quote → submit → separate worker → stored PNG/download → ledger,
затем настоящий Compose restart, повторное скачивание с тем же hash и чужой аккаунт denied.
Секретные synthetic fixtures только RUNNER_TEMP; screenshots не содержат cookies/password.
Последний SHA/проверки — PR/Checks; наличие сценария не означает его выполнения.
