# P0 · Admin provider actions require visible reauthentication

## Owner-observed problem and verified cause

Owner account `spikeal@mail.ru` on local D2-R2 test installation
`127.0.0.1:18084/admin/providers` had existing
`connections.read`, `connections.write`, `secrets.bind` and ACCESS owner
grants. Server-side provider table still contained no configured platform
DeepSeek connection. UI Save/Verify/Policy actions were implicitly disabled
whenever a **separate password field at the bottom of the right-hand card**
was empty. Users could paste a valid provider key in the left card and
the Save button appeared inert. The disabled controls sent no HTTP request,
so logs could not explain the apparent failure.

## Fix (client only)

- Shared current-account password confirmation is now a prominent section
  **above** both provider cards, at the beginning of the workflow on desktop
  and phone.
- This is the password used to sign into IZO ASA, **not** an API key.
- With a key entered, clicking Save while password is missing produces
  an inline, readable error, focuses the password field, and preserves
  the secret field locally without sending a request.
- Verify and Save settings behave similarly; Verify remains disabled
  until a key is configured. Genuine busy actions remain disabled.
- After any attempted authorized mutation the password is cleared;
  errors from reauthentication remain explicit. API secrets are
  never displayed, stored in localStorage or included in screenshots.
- Server-side reauthentication, CSRF, same-origin, staff permission checks,
  revision CAS, encryption and audit are **unchanged**.

## Local acceptance

- Production Vite + TypeScript build PASS on Windows D2-R2.
- 18/18 Playwright checks on laptop and phone, including new
  no-password click, focus feedback, zero POST, valid save, verified
  key status, policy update, wrong-password error, mobile fit and
  pre-existing admin/credits regressions.
- Repository hygiene, docs routing and generated contracts must pass
  on exact Git SHA; required GitHub CI and independent review remain
  separate acceptance gates.
- No changes to any Docker volumes or to existing owner account grants
  are permitted for this UX patch. No real API calls are needed to
  verify the purely visual/form defect.

## Release hold

Stacked on current PR #283 HEAD
`c937e50bd3aeab1ee876b63b5ceabc64843827a6`, which itself is based on
unmerged PR #282/#281/#280/#279. Do not merge any of these PRs into main
without explicit owner approval and applicable required CI.
