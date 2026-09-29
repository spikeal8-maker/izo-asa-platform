# Entitlements · локальная карта домена

Entitlements владеет versioned plan policy, default/assignment resolution и server preflight. Он определяет,
разрешена ли capability и какие конечные quota/size/cost bounds применяются. Он не является billing system,
provider registry или staff-role engine.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| Plan schema / immutable revisions | `schemas.py`, `repository.py` | `test_entitlements.py` |
| Effective plan / assignments | `service.py` | `test_entitlements.py`, `test_entitlements_http.py` |
| Image admission policy | `policy.py:evaluate`, `service.py:assess_image` | `test_entitlement_boundaries.py` |
| Own entitlement HTTP | `routes.py` | `test_entitlements_http.py` |
| Migration/history guards | migration `0005_entitlements` | `test_entitlement_migration.py` |

## Инварианты

- plan не назначает staff permissions и не переписывает Credits balance;
- capability allowlist и numeric bounds проверяются сервером; пустое/нулевое ограничение не означает unlimited;
- effective revision snapshot сохраняется для принятого Job и не меняет прошлую операцию задним числом;
- preflight сам по себе не является reservation: atomic admission выполняет Jobs вместе с Credits/Media;
- stale/foreign usage snapshot не трактуется как нулевое использование;
- provider availability и техническая capability поддержка пересекаются с plan policy, но не принадлежат plan.

## Текущие интеграции

Jobs уже использует entitlement assessment при admission, Credits даёт available balance, Media участвует в
storage/output usage. Поэтому local map не описывает их как «будущие отсутствующие сервисы».

- plan/quota/capability access → `api.entitlements`;
- atomic Job admission/counters → `api.jobs`;
- provider protocol/availability → `api.provider_execution`;
- ledger reserve/settle → `api.credits`.

Коммерческие тарифы/покупки и будущие modality-specific limits остаются отдельными пакетами. Историческая
подробная версия сохранена в `docs/history/local-maps-before-DOC-004C/entitlements.md`.
