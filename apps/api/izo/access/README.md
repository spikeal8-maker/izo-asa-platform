# Access ownership map

`izo.access` owns **staff permission delegation**, not user authentication and not another role system.

## Owns

- A finite allowlist of global delegable permissions.
- Provenance for permissions issued through ACCESS-001.
- Explicit delegation ceilings for privileged operators.
- Exact operation-id replay receipts for grant/revoke.
- Fresh-password confirmation and last `access.manage` protection.
- Initial owner enrollment only through an explicit local bootstrap command.

## Does not own

- Account/session/password state: `izo.accounts`.
- Credit limits or ledger writes: `izo.credits` / `izo.admin`.
- Plan policy values: `izo.entitlements`; SETTINGS-002 consumes `plans.write` later.
- Provider/catalog configuration: CATALOG-002 consumes catalog permissions later.
- Object/tenant scopes: ACCESS-001 exposes only `scope=global` until downstream APIs can enforce narrower scopes.

## Runtime invariants

`account_permissions` remains the materialized authorization source used by existing consumers. `staff_access_grants` records provenance and expiry; both rows change in one transaction. HTTP callers cannot create wildcards, arbitrary permission names, delegation ceilings, permanent grants, or self-escalation. Revoking the last effective `access.manage` holder is refused under a serialized access-state lock.

Read `service.py` for mutation semantics, `permissions.py` for the registry, and `0010_access.py` for durable storage. Targeted tests: `test_access.py`, `test_access_http.py`, `test_access_boundaries.py`.