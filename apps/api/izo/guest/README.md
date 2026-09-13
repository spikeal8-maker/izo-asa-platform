# Guest · локальная карта домена

GUEST-001 даёт один ограниченный image trial до регистрации. Он **не создаёт второй Jobs/Media/Credits runtime**.

| Задача | Owner | Tests |
|---|---|---|
| Guest cookie / session / claim | `accounts/guest_service.py`, `accounts/guest_tables.py` | `tests/test_guest.py`, `tests/test_guest_http.py` |
| Trial credits | `credits/trial.py` | `tests/test_guest.py` |
| Guest HTTP orchestration | `guest/routes.py` | `tests/test_guest_http.py` |
| Result bytes before claim | `guest/media.py` | `tests/test_guest_http.py` |
| Normal job admission/execution | `jobs/service.py`, existing worker | existing Jobs tests + guest tests |

## Инварианты

- Guest bearer физически отделён от `account_sessions` и не является обычной auth-session.
- Guest всё равно получает server-owned `accounts.id`; Jobs, Credits и Media продолжают использовать существующий owner key.
- Один guest-session может принять только один новый generation operation; exact replay того же operation ID безопасен.
- Guest capability ограничен `test.image.v1`; внешний provider spend в GUEST-001 запрещён.
- Trial credit создаётся только внутренней server-командой, один раз, с отдельным immutable ledger kind/reason.
- Claim не копирует job/asset/wallet: к тому же `accounts.id` добавляется email/password identity и обычная session.
- Claim блокируется, пока guest job остаётся active.
- Guest session rate-limited по server-derived network key; client не задаёт owner, budget, provider или price.

Frontend entry: `apps/web/src/features/studio/GuestTrial.tsx`. При регистрации `AccountPage.tsx` использует `/api/v1/guest/claim`, если guest-session ещё действительна.
