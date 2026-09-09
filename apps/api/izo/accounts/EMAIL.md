# AUTH-002 · подтверждение почты, сброс и смена пароля

Серверная реализация на существующих Account/Identity/Session; миграция `0003`.
Это закрытый dev/test этап. Только тестовая доставка, **не SMTP и не публичный запуск**.
Верификация email/recovery реализуются здесь. Смена адреса, linking/unlinking и signed
Telegram/MAX пока НЕ реализованы: это оставшаяся часть общей карточки AUTH-002/PLATFORM.
Экран `/account/connections` только читает текущую email identity и показывает ограничения.

## API и формы

| POST /api/v1/auth/... | Вход / доступ | Результат |
|---|---|---|
| `email/verification/request` | `{}`, session + CSRF + Origin | 202; тестовое письмо для адреса своего аккаунта |
| `email/verification/confirm` | `token`, та же account identity + CSRF | 204; verified_at в PostgreSQL |
| `password/forgot` | `email`, строгий Origin, без session | Одинаковые 202/body для известного/неизвестного/неподтверждённого/ограниченного адреса |
| `password/reset` | `token`, `password`, `confirmation`, Origin | 204; пароль заменён, все старые sessions/proofs отозваны; без auto-login |
| `password/change` | `current_password`, новый пароль дважды, session/CSRF | 204; повторная проверка текущего пароля, отзыв всех сессий |

Формы `/verify-email`, `/password/forgot`, `/password/reset`, `/account/security` используют
общий HTTP transport. Ссылка содержит proof в fragment, не query: браузер убирает fragment
из адресной строки, сохраняет только в памяти компонента. GET/открытие ссылки/почтовый
scanner не потребляют proof. Пароль и proof не пишутся в browser storage или URL возврата.
Referrer policy страницы — no-referrer. При отсутствии сессии подтверждения нужно войти
именно в свой аккаунт и повторно открыть исходную ссылку. Это не незаметное связывание
предварительно зарегистрированного кем-то аккаунта с владельцем почты.

## Данные и транзакции

`account_challenges`: случайный UUID selector, purpose, hash доказательства, снимок
identity/password binding, expiry, attempts, consumed/cancelled. Отдельная
`account_test_mail` хранит только намерения и ID, **не пароль или открытый token**.
Proof: HMAC-SHA256 отдельного IZO_RECOVERY_SECRET + domain/purpose/random selector.
Секрет вне БД; hash полного proof находится в БД. Отдельный TEST renderer восстанавливает
письмо после restart; ротация секрета инвалидирует старые proofs без fallback.
Это не универсальная промышленная система доставки или secret manager.

До подтверждения email reset не разрешён. Security lock/deletion не снимаются сбросом.
Verification проверяет владельца и CSRF. Правильный proof потребляется только один раз
под блокировкой account → session (где нужна) → challenge. Счётчик ошибочных proof-попыток
коммитится до возвращения ошибки. Новый reset request НЕ отменяет уже выданную ссылку:
неавторизованный посетитель не может постоянно делать рабочую ссылку недействительной.
Успешная замена пароля атомарно обновляет password, отзывает sessions/другие proofs,
записывает audit и тестовое notification intent. Ошибка транзакции отменяет всё.

Общий `repository.account_by_id(lock=True)` сначала берёт блокировку accounts отдельным
SELECT, затем читает JOIN credentials новой SQL-командой. Это необходимо для свежего
пароля после ожидания блокировки при READ COMMITTED; один блокирующий JOIN мог прочитать
старый снимок присоединённой таблицы. Реальная PG-проверка ждёт Lock через pg_stat_activity,
не рассчитывает на случайную задержку sleep.

Параметры: lifetime600s, максимум5 неверных попыток на selector, максимум3 запросов
на адрес/account за окно существующего rate policy. Предел расхода KDF сохранён.
Это fixed-window limiter, не готовая DDoS-защита. Ответы forgot одинаковы и имеют
одинаковую форму DB-записи; постоянное время DB и полная защита от timing enumeration
не заявляются. Ранее выданные права/баллы не появляются после подтверждения.

## Проверка локального тестового стенда

Рабочая ветка: `auth/email-recovery`. На новом checkout обычный bootstrap генерирует
раздельные auth/recovery secrets и включает ТОЛЬКО test delivery. Старый .env обновляется:

```sh
python tools/bootstrap.py --recovery-only
docker compose up --build --wait
```

Существующие secrets и режим disabled не заменяются. Без настроенного recovery канала
эти API возвращают 503; обычный auth продолжает работать. Runtime production остаётся
закрытым. Никаких реальных писем/платных API при обычном запуске/тестах.

После запроса письма оператор читает его по UUID аккаунта, показанному серверным API.
`python -m izo.accounts.test_mail --help` описывает `--account` и обязательный
`--show-sensitive`. Команда запускается в API-контейнере, выводит тестовую ссылку/код;
вывод нельзя публиковать в issue, логе CI или artifact. HTTP mailbox endpoint отсутствует.
Настоящая SMTP/API-доставка требует отдельного разрешения, адаптера, доставки/уведомлений,
retention, мониторинга и проверки публичного origin/HTTPS.

## Экономная проверка

Ближайшие tests: `python -m pytest tests/test_email_proofs.py tests/test_email_boundaries.py`.
После schema/route изменения: `python tools/export_contracts.py` и `--check`; generated
JSON не писать вторым контрактом вручную. UI: `email-security.spec.ts`, phone+laptop,
полная QHD/4K матрица перед приёмкой. Общий CI не отключается.

`tools/email_acceptance.py before/after` — только opted-in изолированный CI/PostgreSQL.
Проверяет конкурентное употребление proof, свежесть credentials после PG-lock и реальный
restart с прежними pending/consumed proof/session. Синтетические секреты между фазами
только в закрытом RUNNER_TEMP; не public artifact. Fixtures удаляются по проверенным ID.
Unit SQLite не доказывает PG locks. Browser fake API не является real browser+DB E2E.

Не считать завершёнными: real email delivery, MFA, linking/unlinking/смена адреса,
полный security audit, production rate/trusted-proxy policy, cleanup старых challenge/mail
intents и общий ограниченный доступ по всем ещё отсутствующим доменам. Это явные gates,
не разрешение использовать test mailbox в открытом сервисе.

Опорные первичные источники (проверены 2026-09-08):
- https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html
