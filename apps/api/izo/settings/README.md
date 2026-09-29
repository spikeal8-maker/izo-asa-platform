# SETTINGS-002 · typed basic PlanPolicy lifecycle

Этот модуль управляет только уже существующим `PlanPolicy` basic-плана. Он не создаёт универсальное key/value-хранилище, provider settings, secrets или вторую конфигурационную БД.

Source of truth остаётся в Entitlements:
- `entitlement_revisions` — immutable revisions;
- `entitlement_default` — текущая basic revision + optimistic version;
- `entitlement_changes` — idempotency/audit receipts.

## Ownership

`schemas.py` — строгие request/response contracts.
`service.py` — current/preview/publish/history/rollback поверх Entitlements.
`routes.py` — `/api/v1/admin/settings/basic*`, строгие query/origin/CSRF boundaries.

Permissions:
- `plans.read`: current, history, preview;
- `plans.write`: publish, rollback;
- provisioning этих permissions принадлежит ACCESS-001.

## Invariants

Empty/zero values deny. Если `capability_ids` непустой, publish блокируется без executor, active jobs, submission window, storage, image size и `max_action_credits`.

`preview` ничего не пишет. `publish` создаёт новую immutable revision и атомарно делает её default. `rollback` не изменяет старую строку: он публикует новую revision с прежними значениями.

Apply mode `V`: новые quote/job читают новый default; уже принятые jobs сохраняют свои plan/execution snapshots. Credits, существующие файлы и ledger history не переписываются.

`P-01 plan.max_action_credits` — внутренний descriptor существующего safety field `PlanPolicy`; это не объявление нового S-21 из полного будущего settings catalog.

## Agent routing

Validation/diff → `schemas.py` + `service.py` + `tests/test_settings.py`.
HTTP guards → `routes.py` + `tests/test_settings_http.py`.
Не читать providers/catalog/media ради изменения label или basic policy rule. Не добавлять secrets/endpoints сюда — это будущий CATALOG-002.
