# Chat owner

Chat owns account-scoped DeepSeek and OpenRouter credentials, durable text
Thread/Message/Request, provider-neutral streaming lifecycle and the
`/api/v1/chat/*` HTTP boundary. OpenRouter uses a fixed API origin and a
bounded, cached text-model catalog. Dynamic OpenRouter pricing is external USD
metadata; the Admin catalog owns informational RUB display prices. Missing
RUB prices remain unknown, never free or an implied platform debit.

The API service is the sole executor. The browser never receives a provider key, provider URL,
ciphertext, database owner selector or paid retry authority. PostgreSQL stores encrypted
credential material and chat state; the AES-GCM root key is supplied only through the API
runtime environment and is intentionally absent from database backups and preview archives.

`IZO_ENVIRONMENT=test` may inject `FakeDeepSeekProvider`; development never silently falls
back to it. A failed/unknown real execution is persisted as a non-success terminal state and
is not automatically submitted again.

Before an OpenRouter POST, the request receives a durable unknown-outcome marker.
An uncertain response, disconnect or executor restart preserves it; another
request in that thread is rejected while exact request-ID replay remains safe.
The preview has no in-app reconciliation yet. The user must check the provider
result/charge before manually trying anything elsewhere. The current Compose
preview uses one API worker; a multiworker runtime needs a lease/fence before
scaling this execution path.

Chat bounds live in `schemas.py`; published DeepSeek policy and informational
RUB display prices live in `../catalog/`. UI consumes server policy and catalog
endpoints. The provider key is never sent to the browser after submission.
The server adds a Russian reply preference while respecting an explicit user
language request. Image attachment and generation paths are not implemented in
this package; the browser must not present them as working Chat actions.
