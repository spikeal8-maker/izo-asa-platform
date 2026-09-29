# Jobs · локальная карта домена

Jobs — общее durable-ядро для diagnostic и внешних executors. Оно владеет quote/admission, job state,
attempt/lease/fence, cancellation intent, reconciliation и связью с Credits/Media. Provider HTTP contract
не дублируется здесь: fal adapter — `../providers/`, paid lifecycle — `provider_execution.py`.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| Capability catalog / quote / admission | `catalog.py`, `service.py` | `test_jobs.py`, `test_jobs_http.py` |
| Attempt / lease / fence / completion | `execution.py` | `test_jobs.py`, `test_jobs_boundaries.py` |
| Storage uncertainty / restart | `recovery.py` | `test_jobs_recovery.py` |
| fal paid request lifecycle | `provider_execution.py` + `../providers/fal.py` | `test_provider_jobs.py`, `test_fal_provider.py` |
| Schema / durable provider call | `tables.py`, migration `0009_provider_calls` | `test_jobs_migration.py` |

## Общие инварианты

- Account / Credits / Jobs / Media остаются общими для всех executors;
- browser не задаёт owner, цену, executor, connection, credential, request ID, object key, attempt или fence;
- quote ещё не резервирует средства; admission повторно проверяет policy/usage/balance и фиксирует hold/job атомарно;
- stale fence не завершает новую попытку; готовый Media result и settlement финализируются один раз;
- unknown external outcome не превращается в blind retry или автоматический refund;
- выключение новых admissions не уничтожает обязанность reconcile уже принятого внешнего request.

## Executors

`test.image.v1` — deterministic regression executor без network call. `fal.flux2.klein.4b` — внешний executor,
использующий то же ядро Jobs/Credits/Media. Актуальные capability и product price берутся из `catalog.py`/policy,
а не из этого README. Реальный fal key/spend по умолчанию не разрешён.

Provider request identity и cost metadata находятся в `generation_provider_calls`; secret там не хранится.
Перед внешним POST durable intent фиксируется сервером. Потерянный submit-response без request ID сохраняет
liability для operator review и не создаёт второй paid request. Известный request ID продолжается после restart.

## Когда расширять контекст

- только Job state/admission → оставайся в `api.jobs`;
- provider HTTP/status/result/cancel/request ID → `api.provider_execution`;
- reserve/settle/release → `api.credits`;
- asset/S3/ticket/hash → `api.media`;
- plan/capability/quota → `api.entitlements`.

Block-level operations находятся в `docs/BLOCK_MAP.json`; `tools/context.py` возвращает owner/symbol/anchor.
Подробные исторические критерии JOBS-001 не являются рабочей инструкцией: Git history/reviews сохраняют provenance.

Проверка после локальной Jobs-правки начинается с tests выбранного block/route; PostgreSQL/S3/restart остаются
общим CI gate для затронутых durable semantics. SQLite unit не доказывает locking/restart.
