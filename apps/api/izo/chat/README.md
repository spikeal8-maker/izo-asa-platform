# Chat owner

D1 owns only account-scoped DeepSeek credentials, durable text Thread/Message/Request,
provider-neutral streaming lifecycle and the `/api/v1/chat/*` HTTP boundary.

The API service is the sole executor. The browser never receives a provider key, provider URL,
ciphertext, database owner selector or paid retry authority. PostgreSQL stores encrypted
credential material and chat state; the AES-GCM root key is supplied only through the API
runtime environment and is intentionally absent from database backups and preview archives.

`IZO_ENVIRONMENT=test` may inject `FakeDeepSeekProvider`; development never silently falls
back to it. A failed/unknown real execution is persisted as a non-success terminal state and
is not automatically submitted again.

Limits and model policy live in `settings.py`. UI code consumes the public policy endpoint
rather than duplicating provider capability rules.
