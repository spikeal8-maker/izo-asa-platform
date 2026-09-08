# Фактическое состояние IZO ASA

8 сентября 2026. Новый ограниченный шаг: AUTH-002 / email confirmation + password recovery.
База `f09c48eba527ddeb167f02f225e3263f02e74fa3` (PR #4), отдельная ветка `auth/email-recovery`.
Main/предыдущие PR/старый сайт/пользовательская БД/GPU/реальные ключи не изменяются.
Ни merge, ни deployment, ни real SMTP/API вызовы этим шагом не разрешены.

## Написано

Миграция0003: одноразовые email proofs и secret-free TEST mail intents поверх существующих
Account/Identity/Session. Пять API для запроса/подтверждения адреса, запроса восстановления,
сброса и смены пароля. Старые0001/0002 не меняются. Новый proof не создаёт новую identity.
Пароль/отзыв sessions/proofs/audit атомарны, неизвестные/неподтверждённые адреса дают
одинаковый ответ, security restrictions не снимаются. Отдельный recovery secret,
срок/attempt/rate limits, purpose/binding, отсутствие открытых токенов в DB/mail metadata.

Тонкие формы verify-email/password-forgot/reset/security; connections только read-only.
Убирается fragment из адреса, proof не расходуется на GET и не хранится в browser storage.
Studio/gallery/баллы остаются DEMO. Новый дизайн здесь не утверждался и не перерабатывался.

Уточнён общий account lock/read: сначала блокируется account, потом свежий SELECT
читает присоединённые credentials. Это важно для конкуренции login/reset. Старые auth
API и защитные tests сохраняются. Новых зависимостей, live sender и второго auth ядра нет.

## Проверки

Локально на Python3.13.5/FastAPI0.128.2 прошли 35 новых HTTP/service/boundary cases;
исходные используемые auth-модули и root factory сверены по Git blob SHA. Исходники
доставлены через connector, полного git clone нет. Новые TS/TSX проверены локальным
parser, не полноценной npm-сборкой. В этой среде нет Docker/PG; SQLite не доказывает locks.

OpenAPI сгенерирован существующим инструментом из кода; полный CI на lock-версиях
должен отдельно подтвердить contracts, весь Python suite, frontend и PG/HTTP/restart.
CI дополнен `email_acceptance.py` before/after вокруг уже существующего down/up:
реальные PG-lock wait, конкурентный consume, сохранность pending/consumed proofs,
verified identity и отозванных sessions. Fixtures синтетические, в закрытом RUNNER_TEMP,
не artifacts. Итоговый source SHA/точные результаты закрепляются в PR после чтения
проверок; успех прошлой версии не переносится на новый коммит.

## Что не объявлено готовым

В большой карточке AUTH-002 ещё остаются смена адреса и linking/unlinking identities;
PLATFORM требует проверки подписей настоящих Telegram/MAX. Последний email-способ
не удаляется через UI/API в этой версии; отсутствие такого endpoint не равно готовому
сервису linking. Real SMTP, MFA, public HTTPS/edge/rate/load, cleanup/retention proofs
и независимый security review не выполнены. Recovery пока только закрытый dev/test.

AUTH-001 аккаунты/сессии реализованы ранее; CREDIT/ENTITLEMENT/ADMIN, MEDIA/JOBS,
реальные providers/local worker и пользовательская облачная галерея ещё впереди.
README и accounts/EMAIL описывают запуск этой ветки. NEXT остаётся единственным планом.
Следующий полезный серверный scope — CREDIT-001 (его зависимость AUTH-001 уже реализована);
оставшиеся identity-операции нельзя отмечать закрытыми ради продвижения к генерации.
Защита main и независимая приёмка — отдельные незакрытые gates; эта ветка их не включает.
