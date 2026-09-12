# ACCESS-001 · self-review

Base: frozen LINEAGE-001 source `a1de4b8fc551ba9b5ce3d1d88da7f1eaf378cd0e`.
Working branch: `access/staff-delegation`. Scope: `tools/scopes/access-001.json`.

## Реализовано

- Новый Accounts-owned control layer `izo.access`: provenance grants, delegation ceilings, immutable operation identity и singleton serialization state.
- `0010_access` — additive migration после `0009_provider_calls`; существующий `account_permissions` остаётся materialized authorization source для всех старых consumers.
- HTTP: `/api/v1/admin/access/me`, subject read, grant и revoke. Actor берётся только из session; caller не задаёт actor/role/ceiling.
- A-28 `/admin/access`: permission-aware навигация, поиск только при `users.read_limited`, прямой UUID read при `access.read`, mutation form только при `access.manage`.
- Existing AdminPage получает только `access.read` (не `access.manage`) через `/admin/me` и показывает ссылку A-28 при наличии этого read permission.
- Initial owner создаётся только явным isolated bootstrap; signup/startup не получает staff permissions.

## Security invariants

- Только фиксированный registry известных permissions и только `scope=global`; wildcard/object scopes отсутствуют.
- HTTP grant всегда finite: 5 минут–30 дней и не длиннее actor delegation ceiling.
- Fresh password + CSRF/same-origin; credential/session/access rechecked после KDF внутри mutation transaction.
- Self-delegation запрещена; unmanaged permission нельзя молча захватить в ACCESS provenance.
- Exact operation replay возвращает тот же receipt; изменённый payload/actor/target даёт conflict.
- `access.manage` требует покрывающий `access.read`; `access.read` нельзя отозвать, пока действует `access.manage`.
- Last-owner guard считает только active+verified permanent manager с permanent matching ceiling/materialization; finite manager не предотвращает lockout guard.
- Access operation rows append-only в PostgreSQL; denial/operation audit не содержит password/raw secret.

## Verification до commit

- ACCESS domain + migration/boundary: **22/22 PASS**.
- Admin/access/docs/state targeted set: **83/83 PASS**.
- `tools/check_docs.py` — PASS; state `ACCESS-001 → SETTINGS-002`, 26 blocks, 16 routes.
- Routing corpus: **60 cases**; новые RU/EN access grant/revoke/UI phrases закреплены regression-cases.
- Web production build/typecheck — PASS; OpenAPI TypeScript generated from pinned Python 3.13 contract.
- A-28 Playwright: **30/30 PASS** на 10 viewport/HiDPI profiles; retry сохраняет operation ID и очищает password.
- `py_compile` для access domain/migration/acceptance — PASS; `git diff --check` — PASS; mojibake/`???` scan — clean.
- PostgreSQL acceptance включён в Foundation CI before/after Compose restart: replay, materialization, append-only receipt, finite-owner guard, persistence и permanent-owner rotation.

## Ограничения локальной среды

Windows full pytest не является authoritative: глобальный network-ban ломает `asyncio.socketpair()`/TestClient; global Python 3.11 также отличается от locked FastAPI/Pydantic/Pillow. Эти baseline failures не маскировались изменением tests/conftest. Финальные HTTP/OpenAPI/PostgreSQL результаты должен подтвердить locked GitHub Foundation CI.

## Non-goals

Не добавлены generic RBAC roles, wildcard permissions, object/tenant scopes, HTTP delegation-ceiling mutation, login-as-user, secret viewer или live provider action. Jobs/Credits/Media/Fal runtime не переписывались; live fal.ai call/spend отсутствует. Старые OpenRouter PR остаются reference-only.

**SELF_REVIEW PASS · FULL GITHUB CI PENDING · MERGED NO · DEPLOYED NO**
