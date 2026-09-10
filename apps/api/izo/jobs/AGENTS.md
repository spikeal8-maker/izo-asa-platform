# JOBS: исполняемый серверный сценарий

Наследует корневые и backend-правила. Один ближайший тест после правки; полный CI перед приёмкой.

- DTO/цена/тестовый флаг: schemas.py, catalog.py; tests/test_jobs_http.py.
- Quote и атомарный приём: service.py; tests/test_jobs.py.
- Claim/fence/завершение: execution.py; tests/test_jobs_recovery.py.
- Истёкшие попытки и неизвестный S3 outcome: recovery.py; тот же recovery-test.
- Отдельный процесс: worker.py; tools/jobs_acceptance.py в изолированном Compose.
- Файлы/квоты принадлежат media/outputs.py, media/repository.py; не второй файловой базе Jobs.

Accounts блокируется ПЕРЕД Job. Политика, actual usage, reserve Credits, reserve Media,
Job и outbox фиксируются в одной транзакции. Нельзя исполнять один лишь preflight
admission_reserved=false, читать usage из клиента или сначала commit-нуть деньги.

Браузер не присылает цену/owner/executor/object key/attempt/fence. Он получает quote
на 120 секунд и подтверждает его ID; operation_id идемпотентен. Старый retry возвращает
записанное задание, а не новый резерв. Изменённый запрос требует нового quote.

Ни codec, ни S3 не выполняются при удерживаемой SQL-транзакции. Сначала фиксируется
sealed output, затем put; неизвестный ответ сохраняет резерв. Reconcile только читает
сохранённый объект; после пяти неудач фиксируется потребность в разборе, не paid retry.
Просроченный fencing token не финализирует задачу. Cancel до seal освобождает оба
резерва; после seal это запрос, не обещание возврата.

`test.image.v1` остаётся чистым диагностическим адаптером и только он может автоматически
вернуться в очередь после истёкшей незаписанной попытки. Внешние AI живут в собственных
provider pools и adapters. Для них execution snapshot сохраняет connection/model/format/price;
истёкшая running-попытка считается неопределённым внешним исходом и НЕ переотправляется.
Provider key не хранится в Job и не доступен API/UI. HTTP worker-команд нет.

Не читать все PRODUCT/ADMIN ради одного error code. Не менять старые миграции,
ослаблять guards/тесты или увеличивать scope вместо исправления. Test credentials
только в закрытом RUNNER_TEMP; не logs/artifacts. Job-worker — серверный процесс,
не домашний GPU-агент и не механизм выдачи БД клиентам.
