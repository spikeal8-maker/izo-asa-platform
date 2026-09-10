# SETTINGS-001 · typed lifecycle для используемого basic plan

Этот пакет не создаёт универсальный JSON-конфигуратор и не реализует S-01…S-66.
Он даёт A-27/AD-08 lifecycle только полям, которые уже существуют в `PlanPolicy` и
реально читаются Entitlements/Jobs/Media: S-10…S-15, S-17, S-22 плюс действующий
per-action credit ceiling из той же typed policy.

Source of truth остаётся `entitlement_revisions` + `entitlement_default` +
`entitlement_changes`. Вторых таблиц настроек нет. Draft живёт у клиента до preview;
publish создаёт immutable basic revision и атомарно делает её default. Rollback не
переписывает старую строку — он публикует новую revision с выбранными прежними values.

## HTTP

- `GET /api/v1/admin/settings/basic` — effective default policy + descriptors.
- `POST .../preview` — strict validation, diff, REQ и impact; без записи.
- `POST .../publish` — `plans.write`, CSRF, operation_id, expected_revision и reason.
- `POST .../rollback` — новая revision прежних values; ledger/files/jobs не откатываются.
- `GET .../history` — immutable basic revisions, без secrets.

Ноль/empty означает deny. Если `capability_ids` непустой, публикация блокируется пока
нет executors, active_jobs, submissions, storage, image_sizes и max_action_credits.
`upload_bytes=0/input_count=0` допустимы: image-from-text может работать без uploads.

Apply mode V: новые quote/job используют новый default. Уже принятый job хранит свой
plan/execution snapshot и не переписывается. Это уже проверяется CHANGE-001/JOBS; этот
модуль не добавляет kill текущих jobs.

## Для агента

Правка validation/diff -> `schemas.py`, `service.py`, `tests/test_settings.py`.
Не читать provider client/галерею ради label настройки. Не добавлять secrets или endpoint
редактор сюда: это CATALOG-001. Не изменять прошлые entitlement migrations. Не обходить
`expected_revision` last-write-wins логикой. Не считать self-review независимым аудитом.
