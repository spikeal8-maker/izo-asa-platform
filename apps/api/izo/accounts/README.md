# Accounts · локальная карта домена

Accounts владеет серверной identity, регистрацией/входом, сессиями, password/email security и выдачей доверенного actor для других доменов. Он не владеет балансом, тарифом, заданиями, файлами или provider transport.

| Задача | Основной owner | Ближайшие tests |
|---|---|---|
| Register / login / logout / current session | `service.py`, `routes.py` | `test_accounts.py`, `test_auth_boundaries.py` |
| Password / email verification / recovery | `challenges.py`, `challenge_routes.py`, `challenge_policy.py` | `test_email_security.py`, `test_email_boundaries.py` |
| Session/cookie/CSRF security | `security.py`, `http_security.py` | `test_accounts.py`, `test_auth_boundaries.py` |
| Account persistence / session tables | `repository.py`, `tables.py`, `challenge_tables.py` | migration/account tests |
| Trusted cross-domain access | `admin_access.py`, `credit_access.py`, `entitlement_access.py`, `jobs_access.py`, `media_access.py` | профильные boundary tests |

## Инварианты

- Browser не выбирает account owner, staff actor, permissions или чужую session.
- Session/cookie/CSRF и account state проверяются сервером; permission не хранится как доверенное browser-state.
- Отзыв/expiry сессии не отменяет уже принятую финансовую или provider-обязанность Jobs.
- Пароль, proof/token, raw cookie и секретные audit details не попадают в публичные ответы/логи.
- Account identity одна для Credits, Entitlements, Jobs и Media; второй auth/identity store не создаётся.
- Email сейчас следует документированному mailbox contract; расширение формата не делается «заодно» с UI-правкой.

## Текущие интеграции

Серверные Credits, Entitlements, Jobs и Media уже используют Accounts identity/access boundaries. Web Account/Security pages работают с этими серверными routes; Gallery и Studio не являются demo-заменой auth.

- login/register/session/password/email backend → `api.accounts`;
- account/security UI → `web.accounts`;
- staff lookup/permissions → `api.admin`;
- ledger/balance → `api.credits`;
- plan/capability policy → `api.entitlements`;
- Job ownership/admission → `api.jobs`;
- asset ownership/download → `api.media`.

Для auth-кнопки или формы сначала использовать block/router owner и ближайший test. Большие security/product документы открывать только при пересечении соответствующей границы.

Историческая подробная версия этого README сохранена в `docs/history/local-maps-before-DOC-004D/accounts.md`.
