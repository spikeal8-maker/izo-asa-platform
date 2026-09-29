# PRE-P1-STABILIZATION-001 · evidence

## Boundary

- package base/state head: `2d6b64a520939bf7292e3f35990a96952e1f8a0c`
- frozen E0 source: `811410e3cada4498161415bc279ce9a9f033ab6a`
- package: `PRE-P1-STABILIZATION-001`
- P1 implementation: **NO**
- production deploy/provider spend: **NO**
- migrations: **NO**

## Factual documentation audit

`docs/STATUS.md` incorrectly presented PR #22 / `api/fal-klein-001` as the current baseline and
named an obsolete next package. It now keeps historical checkpoints as history and delegates mutable
state to `CURRENT.md` / `PLAN.json`.

`docs/ARCHITECTURE.md` incorrectly described the API as a Foundation-only shell and migrations as
baseline-only. Current code has Accounts, Access, Credits, Entitlements, Settings, Admin, Catalog,
Media, Jobs, Guest, Chat and provider boundaries, with migrations through `0015_chat_vision`.
## Ruff read-only audit

Audit tool: `ruff 0.16.9`.

- `ruff check . --statistics`: **605 findings**; 288 safe auto-fixable.
- largest classes: I001 197, F811 165, F401 63, RUF059 57, C408 34, BLE001 28.
- `ruff format --check .`: **232 files would be reformatted**, 100 already formatted.
- repository-wide Ruff gate is therefore **DEFERRED_WITH_EVIDENCE**; no mass-format, rule weakening or ignore-list expansion was performed.
- bounded follow-up: Issue #239 `MAINT-RUFF-001`.

## Python dependency audit

Initial `pip-audit 2.10.1` against the pinned runtime lock found exactly one known vulnerability:

- `pydantic-settings==2.14.1` — `CVE-2026-58203`; fixed in `2.14.2`.

The package uses a bounded patch update only: `2.14.1 -> 2.14.2` in `requirements.in` and `requirements.lock`.
Post-update `pip-audit -r requirements.lock --no-deps --disable-pip` reports **No known vulnerabilities found**.
The existing `Dependency Security` workflow now runs the pinned Python audit and retains JSON evidence.
## Unexpected HTTP 500 observability

`apps/api/izo/app.py` keeps the existing safe public 500 payload and now records the unexpected exception with `logger.exception`, correlated by request ID.

Focused evidence:

- HTTP status `500`.
- public body remains only `error.code=internal_error` plus `request_id`.
- `X-Request-ID` is present and equals the public request ID.
- private exception text is absent from the HTTP response.
- server log record contains `exc_info` and the same request ID.
- `tests/test_foundation.py::test_unexpected_http_exception_is_logged_but_not_exposed` — PASS locally after retaining the unit-test external-network deny and allowing only Windows event-loop loopback plumbing.
- direct in-process observability probe — PASS.

## Focused validation

- `python tools/project_state.py verify` — PASS.
- `python tools/check_docs.py` — PASS.
- `tests/test_dependency_security.py` — PASS.
- observability focused test — PASS.
- `git diff --check` — PASS.
- scope check: 14/16 paths maximum, outside scope 0, unapproved sensitive 0.
- combined Windows local HTTP suite is not authoritative because the repository-wide no-network fixture conflicts with Windows AnyIO socketpair lifecycle; authoritative full suite remains GitHub Ubuntu/Python 3.13 CI.

Full exact-head GitHub CI and independent challenge review remain required before canonical main convergence.

## Quality and security audit

Repository-wide Ruff is deferred with evidence, not weakened:

- `ruff check . --statistics`: 605 findings; 288 safe auto-fix candidates;
- `ruff format --check .`: 232 files would be reformatted;
- bounded follow-up: Issue #239 `MAINT-RUFF-001`.

Python dependency audit initially found `CVE-2026-58203` in `pydantic-settings==2.14.1`.
The package is updated to `2.14.2`; the same isolated `pip-audit` command then reports no known
vulnerabilities. Dependency Security now audits the pinned Python runtime lock in addition to npm.

## Observability repair

Unexpected HTTP exceptions retain the existing safe public `internal_error` payload and request ID.
The server now emits `logger.exception(...request_id...)`, so traceback diagnostics stay server-side.
A focused unit test proves the public response excludes the private exception detail.

## Focused verification

- `project_state verify`: PASS
- `check_docs`: PASS
- project-state/review/dependency/docs/observability focused pytest: PASS
- scope check: PASS, 14 files max 16, no outside/unapproved-sensitive paths
- `git diff --check`: PASS
- `pip-audit` after patch update: PASS

## Local OpenAPI check

The Windows controller uses Python 3.11 while Foundation CI uses Python 3.13. Local
`tools/export_contracts.py --check` reports a mismatch on both the stabilization worktree and a clean
detached worktree at exact base `2d6b64a…`. Therefore this mismatch is not introduced by this package.
No OpenAPI artifact is rewritten because no public API surface changed. Exact-head Foundation CI is
the acceptance authority for the generated contract.

## Exact-head CI repair after `4757cec5`

Foundation CI run `36555708548` failed in unit checks for exactly two bounded reasons:

- active-package scope used the state-transition SHA instead of the canonical package base required by the scope contract;
- an older HTTP regression assumed every `izo.http` record was JSON and therefore could not coexist with the new `logger.exception` traceback record.

The repair changes no product runtime. Scope now uses frozen E0 source `811410e3cada4498161415bc279ce9a9f033ab6a`, includes the three state-transition paths, and passes at 14/16 files. The regression test now distinguishes structured request events from the intentional server-side exception record while still proving private query/exception data is absent from the HTTP response and structured request event.

Final exact-head CI remains required after this repair.

## Challenge finding: canonical main checkout

The first stabilization review at `5023f60cfd0c257d3dac915bc725aa00af3f0d14` found one blocker:
after the convergence merge, `project_state verify` on branch `main` would reject the checkout because
`canonical_lineage.working_branch` still named the temporary stabilization branch.

Verdict for that SHA: **REQUEST_CHANGES**.

The bounded state repair changes only `canonical_lineage.working_branch` to `main` and regenerates
`CURRENT.md` through `project_state_model.write_state`. It does not change package status, E0
checkpoint evidence, current package base, product runtime, or P1 scope. The final SHA must be
re-reviewed and must pass `project_state verify` from a branch literally named `main`.
