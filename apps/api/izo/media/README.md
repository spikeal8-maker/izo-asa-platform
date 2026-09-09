# MEDIA-001 · приватные изображения

Основа: ADMIN-001 `16aba52bb5ea811423237915a38d4ec013b92ba6`. Этот модуль использует
существующие Accounts и Entitlements. Он не начисляет и не списывает баллы,
не вызывает AI, не связывает браузерную DEMO-галерею с новой серверной выдачей.
Уже существующее S3-подключение используется без публичных ACL/входящих URL.

## Реализованный ограниченный сценарий

Верифицированный active-аккаунт с конечными upload/storage limits своего effective
плана создаёт намерение загрузки, передаёт байты, получает private asset, читает
свою выдачу и скачивает через короткоживущий session-bound ticket. Ноль баллов,
изменение/истечение плана и недоступный GPU не запрещают чтение сохранённых файлов.
Generation-suspended может читать, но не загружать; security-locked/deletion-pending
не получает эту обычную media-поверхность. Staff не получает чужие media по роли.

### HTTP-контракт

Prefix `/api/v1/media`. Все поля и ответы типизированы в общем OpenAPI.
- `POST /uploads`: operation_id, content_type, byte_size, sha256, width, height.
  Повтор одного payload возвращает тот же ID; другой payload с тем же operation ID
  отвергается. Owner/object key/filename/URL/цена из клиента не принимаются.
- `POST /uploads/{id}/content`: application/octet-stream с фактическими байтами.
  Обязательны session, разрешённый Origin, X-IZO-Request=web и X-CSRF-Token.
- `GET /uploads/{id}`: private состояние, без internal key и secret.
- `POST /uploads/{id}/complete`: `{}`; сверить и завершить уже сохранённый кандидат,
  в том числе после неизвестного ответа S3 или restart. Не повторяет генерацию.
- `POST /uploads/{id}/cancel`: `{}`; отменяет только ещё не записываемый файл.
- `GET /assets?limit=20&offset=0`: private metadata, used/reserved bytes. Limit1…50,
  offset0…10000; глубокий архив/курсор — отдельное расширение, не endless offset.
- `GET /assets/{id}`: metadata своего готового изображения.
- `POST /assets/{id}/download`: `{}`; URL посредника, срок120 секунд, привязка
  к asset и точной session; максимум20 действующих grants на session.
- `GET /assets/{id}/content?ticket=...`: требуется исходная session cookie. Не S3
  presigned URL. Чужой аккаунт/другая сессия/expiry/revoke не получает bytes.

Ответ скачивания attachment, безопасное UUID-имя, image/png, no-store, nosniff,
sandbox CSP и no-referrer. Ticket в БД хранится хэшем. URL нельзя писать в access
logs/analytics; перед public release проверяется конфигурация каждого proxy.
Приватные ID возвращают безопасный not_found. Неправильные параметры не отражаются
в validation JSON. Ошибки конфигурации/S3 не отправляют внутренние сведения.

## Проверка содержимого и конечные пределы

Первый объём: только одиночные PNG/JPEG/WebP, максимум16MiB вход, стороны до8192,
не более16,777,216 пикселей. Реальный decoder сверяет тип/размеры и кадры;
расширение файла/MIME клиента не доказательство. SVG/HTML/GIF/анимации не принимаются.
Нормализация всегда создаёт **новый RGBA PNG** с применением EXIF orientation;
metadata, EXIF/ICC и хвосты исходного файла удаляются. Это не побайтное хранение
оригинала и не обещание сохранения цветового профиля. Не выдавать такую версию за
архивный оригинал. В будущем другие форматы получают отдельные проверенные codecs.

Pillow12.3.0 — единственная новая зависимость, закреплена в input/lock. Decoder
запускается без shell в disposable Python subprocess. Ему не передаются server
secrets из env; whitelisted PATH/PYTHONPATH и два технических флага. Linux:512MiB
address-space,15s CPU; родитель20s wall-time. Два декодера/два media HTTP-request
на процесс; вход/time/output ограничены. Это **не полный OS sandbox, не антивирус
и не распределённый rate limiter**. Native Windows, production workloads и более
строгая OS/egress изоляция требуют отдельной приёмки. Патч не открывает production.

## Транзакции и восстановление

`pending → validating → storing → ready`. Также rejected/expired/cancelled. При
admission резервируется верхняя граница нормализованного PNG (не только размер
сжатого входа). Реальные metadata/активные allocations читаются под owner lock.
Резерв не может превышать plan.storage_bytes; четыре активных uploads/аккаунт,
100 intents за час — консервативные технические caps, не коммерческие тарифы.
Upload TTL900s; validation attempt имеет lease60s и fencing UUID.

Порядок блокировок: Account/session → plan → Media. Никакая DB-транзакция не остаётся
открытой во время декодирования/S3. Перед put фиксируются immutable candidate hash,
size, key и storing. После успешной проверки insert asset, ready/reserved0 и audit
коммитятся вместе. Ошибка аудита откатывает финализацию, но stored candidate остаётся
доступен для /complete. Результат S3 неизвестен — резерв не освобождается автоматически.
Одинаковый retry пишет только тот же sealed candidate; другой hash отвергается.

Pending/не записывавшийся expired validation безопасно истекают; запоздалый decoder
не может seal после отмены/новой попытки. STORING не удаляется expiry job: сначала
сверка объекта. При отсутствии объекта допустим повтор исходных bytes, при наличии
— /complete. Продолжение после restart не полагается на память процесса.
Download проверяет ownership/session/ticket до и после S3 IO. Уже отправленные
байты отозвать невозможно, момент после начала ответа не обещается как atomic revoke.

## Что ещё не реализовано

Нет окончательного удаления ready-assets, lifecycle-orphan purge, папок/полноценной
облачной галереи, A-17/A-18 staff-viewer, thumbnail pipeline, multipart/direct-to-S3,
выходных allocations JOBS и результатов генератора. В данном этапе MIME/владение
и служебная выдача готовы, интерфейс загрузки подключается позже. JOBS должен
резервировать **свои** outputs вместе с credits/job; этот upload allocation не
подменяет атомарную admission для модели. Отмена/удаление готовых файлов потребует
учёта будущих input references/publications; отсутствующий endpoint лучше обхода.

## Приёмка и экономный цикл

```sh
PYTHONPATH=apps/api python -m pytest tests/test_media.py tests/test_media_access.py
PYTHONPATH=apps/api python -m pytest tests/test_media_codec.py tests/test_media_http.py
PYTHONPATH=apps/api python -m pytest tests/test_media_migration.py tests/test_media_boundaries.py
python tools/export_contracts.py --check
```

UnitSQL использует SQLite+real Accounts/Entitlements, in-memory store; codec отдельно
проверяется настоящим subprocess. Это не подтверждение PostgreSQL locks.
`tools/media_acceptance.py before/after` в существующем disposable Compose CI проверяет
HTTP/PG quota race, owner, формат, expired ticket и recovery **реального записанного
S3-объекта после потери ответа и пересоздания контейнеров**. Синтетические cookies
только в закрытом RUNNER_TEMP, не в artifacts. Прежние проверки админки не отключаются.

Источники (проверены 9 сентября2026):
- https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html
- https://pillow.readthedocs.io/en/stable/reference/Image.html
- https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

Данные о фактически выполненных проверках — STATUS и exact-head Checks PR.

## Приращение PR и база проверки

PR этого пакета направляется в `admin/users-compensation` (base16aba52), чтобы
Files changed показывал только MEDIA, а не предыдущие этапы. Оба workflow
сохраняют pull_request для main и дополнительно допускают эту конкретную базу.
Permissions остаются contents:read; audit и прежняя приёмка не ослабляются.
Это не слияние админки или изменение main. При дальнейшем retarget нужна проверка
обоих triggers и точного проверенного SHA. Новых source paths —30, предел30.
