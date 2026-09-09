# Фактическое состояние IZO ASA

Срез: 9 сентября 2026. Source base нового пакета MEDIA-001 —
`16aba52bb5ea811423237915a38d4ec013b92ba6`, `admin/users-compensation`, PR #10.
Main не изменена; слияние и развёртывание не выполнялись.

## Подтверждённый ADMIN-001

Foundation run34327811372/job102389047577 завершён успешно. Предыдущие 495 Python
и270 viewport cases плюс ADMIN_BEFORE_OK/ADMIN_BROWSER_OK/ADMIN_AFTER_OK относятся
именно к admin-base. Реальный браузер прошёл login → поиск → компенсация → баланс;
после Compose down/up проверены сохранность, отсутствие дубля и отзыв permission.
Это не приёмка будущих media endpoints.

## MEDIA-001: реализуемый объём

Подготовлены9 API endpoints: private upload intent/content/status/complete/cancel,
список/metadata assets и короткоживущий session-bound download. Миграция0007_media
добавляет reservations/assets/tickets, не переписывает прежние migrations.
AuthService и EntitlementService общие; Credits не изменяется. Публичных uploads,
user-supplied owner/object URL или admin bypass нет. Квота считает ready bytes и
активные reservations под owner-lock; S3/codec не держат DB transaction.

PNG/JPEG/WebP до16MiB и16,777,216px декодируются отдельным ограниченным процессом
с Pillow12.3.0 и сохраняются очищенным RGBA PNG. Оригинал, EXIF/ICC не сохраняются;
это не архивная копия. Нет animation/SVG/HTML, thumbnails, удаления ready-assets,
cloud-gallery UI, video/audio/3D и generator output. Child limits не полный sandbox.

Неизвестный исход записи удерживает reservation и sealed metadata; complete
сверяет сохранённый объект. Поздняя validation не завершает cancelled upload.
Download требует первоначальной session и ограниченного ticket, проверяется до
и после S3; истечение/revoke не делает файл публичным.

## Проверки и публикация

Исторические локальные80 новых tests прошли на SQLite/ASGI/in-memory store и
настоящем codec subprocess. Исходный пакет повторно проверен по29 hashes.
В этом продолжении добавлена проверка сохранения обоих CI при incremental PR.
Результаты повторного прогона и окончательного GitHub CI относятся только к
реально выполненной команде и фиксируются в exact-head Checks/описании PR.
Наличие acceptance script не означает его успешный запуск.

Прямой network checkout в локальной среде недоступен (DNS github.com). Частичная
материализация и тесты не объявляются полным checkout/lock environment. Полная
проверка должна включать export/typecheck/browser, PostgreSQL/S3 concurrency и
before/after media_acceptance через настоящий Compose down/up. Синтетические
cookies/fixture state только RUNNER_TEMP, не artifacts/логи. Main и production
не затрагиваются. Не переносить зелёный результат предыдущего SHA на новый.

## Ограниченная область и следующий шаг

Пакет30 путей при пределе30: прежние29 + dependency-audit trigger для конкретной
базы admin/users-compensation. PR на эту базу показывает только приращение MEDIA.
Оба workflow продолжают запускаться и для main; permissions read-only, audit
high/critical и прежние tests сохранены. Отдельного обхода защиты или force-push нет.
Визуал, Accounts/Credits business rules, старые migrations, LICENSE не меняются.
Причина прошлой блокировки создания Git tree не установлена; корректность архива
не считается объяснением отказа. PUSHED/TESTED подтверждаются только ответом API.

После подтверждённой media-приёмки — JOBS-001: durable jobs/attempts и атомарная
admission с reservations Credits/Media. Нельзя dispatch по одним лишь разрешениям
Entitlements (admission_reserved=false). Полное независимое review, branch
protection, production secrets/egress, backup restore и реальная почта остаются
открытыми; не заявлять готовность рабочего сервиса или AI-генератора.

INDEX — карта; NEXT — порядок. IMPLEMENTED/TESTED/PUSHED/MERGED/DEPLOYED независимы.
