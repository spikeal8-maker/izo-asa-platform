# SETTINGS-001 agent boundary

Scope: typed basic-plan lifecycle only. Read `README.md`, `schemas.py`, `service.py` and
nearest settings tests first. Existing EntitlementService remains the only writer of plan
revisions/defaults. Do not create generic key/value tables, secret inputs, provider catalog,
or edit all ADMIN S-groups.

Every mutation: server session + plans.write + CSRF + operation_id + expected_revision +
reason. Conflict fails closed. Rollback creates a new revision. Empty/zero stays deny.
Run `pytest tests/test_settings.py` before broad suites; full CI before acceptance.
