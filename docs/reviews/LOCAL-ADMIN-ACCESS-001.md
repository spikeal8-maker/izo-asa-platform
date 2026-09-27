# LOCAL-ADMIN-ACCESS-001 · implementation contract

## Before → after

Before: the Docker Chat Preview admits an explicitly allowlisted account, but an account registered while mail delivery is disabled has no `verified_at`. The existing local owner bootstrap and every staff request reject that account, so its owner cannot reach Admin. A synthetic pre-verified Admin account hides this gap.

After: an operator may designate one exact email account ID with an explicit isolated development/test setting and enroll that account through the existing audited local ACCESS bootstrap. Staff requests for that exact account use its server-held nonfinancial permissions without requiring a mail proof that the preview cannot deliver. Credits and Plans remain verified-only; removing the local setting closes the exception. No identity row is marked verified by this feature.

## Fixed scope

- Package/base: `LOCAL-ADMIN-ACCESS-001` from `codex/chat-ux-001@74bdd8916473975cc0b140feb93bc001f9fffd01`.
- Normal machine scope: at most 16 declared files. Owners: Accounts staff trust, ACCESS bootstrap and invariant, Docker preview setting, targeted tests and local owner maps.
- No signup-time Admin rights, browser permission flag, real email service, Credits/Entitlements bypass, real provider call or production deployment.

## Risk and acceptance

Risk: high (auth and permissions). The pre-fix Docker image refused explicit local enrollment with `verified_active_account_required`. Acceptance proves that audited bootstrap and staff session work only with isolated mode and the exact account ID, default/other-account/non-development modes remain denied, Credits/Plans read, write and delegation remain closed, and the unverified local owner cannot replace the last verified permanent ACCESS owner. Run targeted Accounts/ACCESS/Admin tests, Docker preview smoke, self-review, scope/docs/secret checks and full required CI.

## Self-review and evidence

Verdict: **PASS** for the finite local-access implementation. The exact email account needs both `IZO_LOCAL_UNVERIFIED_STAFF_MODE=isolated` and a matching UUID in development/test; the existing ACCESS CLI remains an explicit operator action, creates permission materialization and delegation provenance in one transaction, and never changes `verified_at`. The shared staff session, ACCESS delegation and owner bootstrap continue to require verified email for `credits.*` and `plans.*`. The local owner cannot replace the last verified permanent ACCESS owner. The local Admin catalog uses existing server permissions and top-bar navigation; no browser-held role was added.

Acceptance evidence: the pre-fix Docker image rejected enrollment with `verified_active_account_required`. Negative tests then exposed Credits and Plans paths through staff sessions and delegation; those paths were closed before final acceptance. The final targeted non-HTTP suite (`test_local_staff`, ACCESS, Admin, catalog, Settings and their boundary tests) passed 107 cases. Local `check_change`, `check_docs`, `project_state verify`, `export_contracts --check` and `git diff --check` passed. A separate read-only local security review reported PASS on the corrected diff; it is not a structured GitHub `APPROVED` review. Required full CI remains the technical acceptance gate.

Docker evidence: `http://127.0.0.1:18080/api/health/ready` returned 200. The existing account `Алекс` was explicitly enrolled with ten nonfinancial rights: `catalog.read`, `catalog.write`, `pricing.write`, `users.read_limited`, `audit.read`, `access.read`, `access.manage`, `connections.read`, `connections.write` and `secrets.bind`. Database inspection found those ten permissions, zero Credits/Plans permissions and unchanged unverified email. The API's staff check and Chat Preview allowlist both admit that account. The old key submission left no `chat_connections` row; the user must enter the provider key again to try Chat. No real provider call or expense was made.

Maintainability delta: 15 changed files in the original 16-file normal scope. New tests live in `tests/test_local_staff.py` (10,016 B); `test_access.py` and `test_admin.py` remain byte-identical to base. All changed handwritten source files remain below 12 KiB/300 lines (largest: `access/mutations.py` 8,507 B, 134 lines); no generated contract or migration changed. The runtime setting is opt-in and the Compose web edge remains loopback-bound. A future externally reachable deployment must omit the local staff settings.

Open verification limit: this environment's browser-control connection did not expose the user's existing browser session, so the local account was verified through the live database and API configuration, not a logged-in UI click. The user should refresh the preview to load the new permissions.
