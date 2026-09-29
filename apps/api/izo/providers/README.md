# Provider adapters · локальная карта

Provider adapter переводит внешний HTTP contract в нормализованные outcomes. Он не владеет Account,
Credits, Jobs, Media, entitlement или UI. Durable lifecycle внешнего request находится в `../jobs/provider_execution.py`.

| Задача | Читать | Test |
|---|---|---|
| fal HTTP/queue/status/result/cancel | `fal.py` | `tests/test_fal_provider.py` |
| paid request lifecycle/restart/refund | `../jobs/provider_execution.py` + jobs AGENTS | `tests/test_provider_jobs.py` |
| provider network/secret process | `../../../../compose.yaml` и jobs worker | compose/CI gates |
| архитектурное правило | `../../../../docs/AI_RUNTIME.md` только нужный раздел | contract review |

## Граница

Adapter получает credential только в provider-worker. Public API/browser не получает provider key или provider URL.
Submit с неоднозначным исходом не считается безопасным отказом. Известный `request_id` reconcile-ится без новой генерации.
Provider output — untrusted input: URL/redirect/size/MIME/dimensions ограничиваются до Media codec/S3.

Product Credits и provider cost — разные величины. Наличие adapter не разрешает live key/spend/production.
