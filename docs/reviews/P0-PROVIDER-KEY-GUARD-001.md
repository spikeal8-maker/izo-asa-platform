# P0 Provider Key Mismatch · verified diagnosis and fix

## Incident evidence — 23 October 2026

D2-R2 isolated localhost:18084, source 01f41f97ff9ad1e623c4ece9a06cb78bf9f20616:

- DeepSeek account credential was configured and enabled, revision 3, but
  verified_at was NULL; HTTP verify returned 422 credential_rejected.
- OpenRouter account credential was not configured: no row in that account.
- Read-only in-container inspection decrypted the account-owned credential
  without printing the secret. Its value carried an unmistakable OpenRouter
  prefix, not the DeepSeek token pattern.
- That saved value returned HTTP 401 both at DeepSeek /models and
  OpenRouter /api/v1/key. Moving this invalid key is not a solution.
- A distinct test DeepSeek token passed genuine DeepSeek /models and
  bounded streaming on both deepseek-flash and deepseek-v4-pro.
- No full secrets or credential fingerprints are committed to Git.

There was no PostgreSQL save outage. The original UI accepted a detectable
cross-provider mixup. A stored unverified status was correct but not useful.

## Bounded implementation

- Python server rejects unmistakeable cross-provider prefixes before
  storing a secret, returning HTTP 422 credential_provider_mismatch.
- Browser presents a localized warning on the provider card, aria-invalid,
  disabled submit and editable field. The backend independently enforces it.
- The oversized ChatCredentialPanel is split into separate popover and
  ProviderCredentialCard components, preserving former behavior.
- Validating the format does not validate the key with the remote provider;
  verified remains false until the real provider accepts it.
- Existing synthetic test keys, personal BYOK, session isolation and
  Graph/SSE are preserved. No migrations, new auth or paid retries.
- Errors and tests do not contain raw keys, ciphertext, nonces or hashes.

## Exact-source verification

- HTTP negative tests: wrong-provider save fails without making a record;
  attempted replacement of an existing verified key cannot disable it.
- Positive tests: own-provider formats remain savable; synthetic keys work.
- Laptop and phone browser tests: inline warning, no POST on mismatch,
  correction enables action, server HTTP 422 gets localized text.
- Existing provider, credential and Chat HTTP tests are regression-covered.
- New test files are named in docs/CONTEXT_MAP.json.
- Screenshot/diagnostic evidence stays in local D2-R2 QA storage.

## Release boundary

Branch is stacked on PR #282 exact parent
311baec81f94ae999d1cc8ae3987a8878ca78f91. That PR depends on
unmerged #281, #280 and #279. No merge to main without owner approval.
No automatic cross-vendor credential migration, impersonation of an owner,
shared paid execution or modification of other Docker projects.

The incorrectly stored key in the current 18084 account remains available
for deliberate replacement through the ordinary authorized Chat UI.
