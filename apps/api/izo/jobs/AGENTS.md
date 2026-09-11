# JOBS / API-001: server execution rules

Наследует корневые и backend-правила. Один ближайший тест после правки; полный CI перед приёмкой.

- DTO/каталог/продуктовый reserve: `schemas.py`, `catalog.py`, `service.py`.
- Claim/fence/Media/Credits completion: `execution.py`; это общее ядро, не provider SDK.
- Чистый test executor: `worker.py`; его retry разрешён только для `test.image.v1`.
- fal lifecycle: `provider_execution.py` + `../providers/fal.py`; отдельный процесс `fal_worker.py`.
- Provider request identity/cost metadata: `generation_provider_calls`, migration `0009_provider_calls`.
- S3 uncertainty после seal: `recovery.py`; повторно читается уже сохранённый object, генерация не повторяется.

Accounts блокируется ПЕРЕД Job. Policy, actual usage, reserve Credits, reserve Media, Job и outbox
фиксируются одной admission-транзакцией. Браузер не присылает цену, owner, executor, connection,
credential, provider URL/request ID, object key, attempt или fence.

## Два capability, одно ядро

`test.image.v1` остаётся deterministic regression-provider и не делает network call.
`fal.flux2.klein.4b` использует тот же Account/Credits/Jobs/Media/Gallery. Нельзя создавать
FalJobs/FalCredits/FalGallery, отдельную авторизацию или provider-specific browser fetch.

fal capability по умолчанию недоступен. Для admission нужны явные `IZO_FAL_ENABLED=true`,
ненулевая цена провайдера в microUSD/MP и max-cost cap. Ключ `IZO_FAL_KEY` и несекретную `IZO_FAL_CREDENTIAL_VERSION` получает только
`fal-worker`; API и test-worker его не получают. Значение ключа не пишется в DB/log/UI/artifacts.
В DB сохраняются только connection/credential reference, request ID, проверенные queue URLs,
state и cost telemetry без secret.

## Paid provider invariant

Перед POST в fal создаётся durable `generation_provider_calls` со state `submitting`.
Если POST мог уйти, но ответ потерян, job переходит в `reconciling/provider_submission_unknown`,
а product/media reservations сохраняются. **Автоматического второго submit нет.** Если request ID
получен и сохранён, новый worker после lease expiry продолжает status/result того же request ID.

Cancel до provider intent может освободить reserve. После provider intent отмена — только запрос:
- HTTP 202 `CANCELLATION_REQUESTED` сам по себе не даёт refund: request мог перейти в execution;
- terminal cancel/release допустим только когда ранее принятая отмена затем подтверждается отсутствием request;
- `IN_PROGRESS` cancellation не обещает остановку; если fal всё же завершил request, обычный
  result → canonical PNG → S3 → settle остаётся источником истины;
- unknown/auth/deadline сохраняют liability для reconcile/operator review, а не делают paid retry.
Новые admission можно выключить/обнулить бюджет без обрыва polling уже сохранённого request ID;
для такого polling всё равно обязателен совместимый credential reference и доступный credential.

Provider output URL не является доверенным transport input. Разрешён только HTTPS host
`fal.media`/`*.fal.media`, redirects не принимаются, body bounded. После download существующий
`media.codec.decode()` повторно декодирует/очищает PNG до seal/S3.

Unit/browser используют fake transport и blocked network. Настоящий AI вызов выполняется только
на тестовом аккаунте с отдельным разрешением владельца, ключом и лимитом расходов. CI ключа не имеет.
Не менять старые миграции, не ослаблять fencing/idempotency/tests и не расширять scope из-за provider.
