# IMAGE-001 / API-001 · серверное рабочее пространство

U-09/U-10 — Studio; U-17/U-18 — ResultPanel; U-19/U-20 — Gallery/AssetPage.
Один серверный Account/Credits/Jobs/Media для test и real provider. `test.image.v1` остаётся
диагностическим исполнителем; API-001 добавляет `fal.flux2.klein.4b` через тот же transport.
Provider capability и jobs выключены серверными настройками/планом по умолчанию.

## Контракт Studio

Studio читает `auth/me`, entitlements и credits. UI показывает только известные image capabilities,
разрешённые policy; сам не выбирает provider URL, key, connection, executor или цену. Quote содержит
серверные prompt/размер/reserve/expiry и `test_only`. Submit после явного подтверждения отправляет
только `quote_id/operation_id` с CSRF. Для fal в подтверждении явно показано, что вызов реальный.

Доступные размеры — пересечение policy и текущего image-контракта 32…512px. API-001 намеренно не
расширяет разрешения до 2K/4K: сначала проверяется provider lifecycle и cost cap. Product Credits и
provider cost — разные величины; UI не вычисляет ни одну из них самостоятельно.

До отправки IDs сохраняются в sessionStorage под account-specific key. Пароли, CSRF, prompt, баланс
и bytes там не хранятся. Потерянный submit-response браузера повторяет тот же operation ID. Серверный
unknown provider-submit — другой уровень: backend никогда не создаёт новый paid provider request без
доказанного pre-acceptance rejection.

`rejectedBeforeAdmission` по-прежнему требует точную пару HTTP status/code. Знакомый текст ошибки,
403/422/429 или server/network failure не являются доказательством, что исходный Job не принят.

Задания poll-ятся последовательно. `provider_submission_unknown`, `provider_auth_required`,
`provider_deadline` и исчерпанный storage reconciliation останавливают автоматический UI poll и
показывают, что нужен разбор существующей операции. Отмена меняет только серверное состояние;
после внешнего submit UI не обещает refund, пока provider outcome не подтверждён.

Gallery остаётся provider-neutral: результат становится обычным private Media asset. Detail получает
session-bound ticket и проверяет PNG MIME/размер/hash. Browser никогда не скачивает fal URL напрямую.

## Что не реализовано этим пакетом

Нет image-to-image, references/masks, webhook callbacks, нескольких provider connections, key-balancer,
автоматического provider failover, production release или коммерческого pricing engine. Настоящий fal
live call не является частью бесплатного CI и требует отдельного ключа/бюджета/разрешения владельца.

## Проверки

`npm run build`; `npx playwright test e2e/studio.spec.ts e2e/provider.spec.ts e2e/gallery.spec.ts`.
Browser fixtures mock только product API. Backend provider contract/restart/cancel/unknown-submit
проверяются Python tests с fake transport; сеть default pytest запрещена. PostgreSQL/S3/restart и
существующий test-image browser path остаются обязательными общими CI gates.
