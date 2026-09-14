# Accounts · email verification/recovery note

Это **короткая live-ссылка**, а не исторический отчёт package. Основная ownership-карта Accounts находится в
`README.md`; подробные старые решения и CI evidence читаются только через `docs/reviews/`/Git history по необходимости.

Текущие invariants email/recovery:
- verification/recovery proofs одноразовые, bounded и server-owned;
- proof/пароль не сохраняются в browser storage, query URL, логах или artifacts;
- forgot response не раскрывает существование чужого адреса;
- reset меняет password атомарно и отзывает прежние sessions/proofs;
- test delivery не является production email delivery;
- signed Telegram/MAX identity, production mail transport и долгосрочный cleanup относятся к отдельным продуктовым/operations пакетам.

Ближайшие tests: `tests/test_email_proofs.py`, `tests/test_email_boundaries.py`, web `email-security.spec.ts`.
Для точной операции сначала использовать `tools/context.py`, а не читать этот файл целиком как package history.
