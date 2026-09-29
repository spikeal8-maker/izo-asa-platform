# SETTINGS-002 · self-review

Base: frozen ACCESS-001 source `fbb3ba01232c0b31682db0f37a070300d95335ed`.
Working branch: `settings/plan-policy`. Scope: `tools/scopes/settings-002.json`.

## Реализовано

- Новый `izo.settings` re-author старого PR #19 на canonical fal lineage; provider/OpenRouter runtime не переносился.
- Source of truth остаётся существующий `entitlement_revisions` + `entitlement_default` + `entitlement_changes`; новой settings-таблицы и migration нет.
- Typed lifecycle только действующего `PlanPolicy`: current, history, preview, publish и rollback.
- `plans.read` обслуживает current/history/preview; `plans.write` требуется только publish/rollback и выдаётся через ACCESS-001.
- Publish/rollback используют optimistic `expected_revision`, immutable revisions и Entitlements idempotency; rollback создаёт новую revision.
- `P-01 plan.max_action_credits` документирует уже существующий safety-field без выдумывания нового ADMIN S-ID.
## Security / contract review

- Caller не передаёт actor, role, provider key или secret; actor берётся только из validated session.
- Mutations используют same-origin + CSRF и повторную `plans.write` проверку внутри Entitlements transaction.
- Query surface fail-closed: duplicate/unknown params и invalid pagination отклоняются.
- Input models остаются strict/extra-forbid. Для HTTP JSON добавлены только boundary validators: JSON arrays → typed `PlanPolicy`, UUID string → `UUID`; numeric/string coercion не включался.
- Найден и исправлен дефект старого SETTINGS-001: strict nested tuples/UUID делали нормальный JSON `POST /preview|publish|rollback` неработоспособным.
- Unknown fields, changed payload с тем же operation ID и stale expected revision fail-closed.
- Preview read-only: не создаёт revision/default change и не выполняет provider call/credit mutation.

## PostgreSQL/restart acceptance

`tools/settings_acceptance.py` запускается после Entitlements fixture: ACCESS owner выдаёт оператору `plans.read/plans.write`, затем HTTP выполняет preview → publish → exact replay/conflict → rollback → history. После проверки exact исходный Entitlement default восстанавливается внутренней versioned command, чтобы SETTINGS не загрязнял последующие JOBS/IMAGE acceptance. После Compose restart проверяются policy hash/default identity, ACCESS permissions и replay старого rollback receipt без повторной записи default.
## Verification до freeze

- SETTINGS domain + boundary: **21/21 PASS**.
- Locked Python 3.13/FastAPI/Pydantic Docker: SETTINGS HTTP/domain/boundary **31/31 PASS**.
- Pinned OpenAPI snapshot: exact byte/semantic match с Python 3.13 `requirements.lock` image.
- Docs/state/settings combined gates, `tools/check_docs.py`, `project_state verify`, `py_compile`, `git diff --check` — PASS.
- Routing: **30 blocks / 17 routes / 64 corpus cases**.
- Web production typecheck/build после нового OpenAPI — PASS.
- Full synthetic test-image run не засчитывался как full gate: 751 tests прошли, 44 failures были только из-за намеренно не скопированных `.github/docs/apps/web/compose` файлов. Authoritative full suite — GitHub Foundation CI.

## Non-goals

Нет generic key/value settings, S-01…S-66 реализации, provider endpoint/key editor, credential storage, pricing/catalog schema, arbitrary effectiveAt, tenant/object scope, live provider call или fal.ai spend. CATALOG-002 остаётся следующим отдельным package.

**SELF_REVIEW PASS · FULL GITHUB CI PENDING · MERGED NO · DEPLOYED NO**
## CI isolation correction

First Foundation attempt `34717496370` proved 795 Python tests and 450 browser tests, and reached `SETTINGS_BEFORE_OK`, but the following ACCESS acceptance failed because the SETTINGS fixture left an extra permanent bootstrap owner. The correction removes only that disposable bootstrap owner's access grants, delegation ceilings and materialized bootstrap permissions before the next acceptance gate; delegated `plans.read/plans.write` on the SETTINGS operator remain for restart verification. Runtime ACCESS/SETTINGS authorization is unchanged.
