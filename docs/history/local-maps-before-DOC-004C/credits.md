# CREDIT-001 — серверный журнал баллов

Основа: `8880dd2084ad43e239391037a707bea43ea763f7`, AUTH-002 email slice. Пакет подготовлен 9 сентября 2026 и публикуется в отдельной ветке `credits/server-ledger`. Результаты текущего source SHA и полного CI фиксируются в PR; локальные проверки не считаются production readiness.

## Что реализовано

`credit_wallets` — проекция баланса и резервов на существующий Account. `credit_ledger` — неизменяемые записи; `credit_reservations` — активные/завершённые резервы. Новая миграция `0004_credits`, parent строго `0003`; старые миграции не переписываются. FK не позволяет каскадно удалить историю вместе с аккаунтом; будущая процедура удаления должна отдельно учесть хранение/обезличивание.

`balance` — несписанные баллы, включая зарезервированные. `available = balance - reserved`. Резерв не окончательное списание. Пример, покрытый тестом: +100 → reserve70 даёт balance100/reserved70/available30 → settle50 даёт balance50/reserved0/available50. Release резерва70 возвращает available100, не начисляет лишние70. Settle0 закрывает резерв без списания.

Все величины — целые баллы, не float, рубли или токены LLM. MAX_OPERATION=1e9 и MAX_BALANCE=9e12 — технические пределы арифметики, не коммерческие тарифы. Тарифы/ежедневные квоты — ENTITLEMENT-001.

## Команды и область доверия

`CreditService` не открывает свою транзакцию и не выполняет commit: методы вызываются внутри `engine.begin()`/unit-of-work будущего Jobs/Admin. Каждая команда использует savepoint; её частичные изменения не сохранятся даже при перехвате ошибки вызывающей стороной. Ошибка внешней транзакции откатывает и баллы. Никаких provider calls в транзакции.

- `grant(conn, account_id, actor_id, Grant, grant_limit=0)`: явный подтверждённый сервером staff actor, активное permission `credits.grant`, конечный доверенный лимит (по умолчанию запрет). Case ID уникален глобально: новая операция по уже обработанной заявке не выдаёт второй grant. Пока разрешены compensation/test_grant. Корректирующее списание и refunds не реализованы.
- `reserve(conn, account_id, Reserve)`: серверный request ID, reservation ID, operation ID и положительная оценка. Требуется active и подтверждённая identity; недостаток available не создаёт ни резерва, ни проводки.
- `settle(conn, account_id, Settle)`: только фактическая стоимость 0…reserved; превышение отвергается, не уводит баланс в минус.
- `release(conn, account_id, Release)`: закрывает существующий резерв без окончательного списания.

**Эти мутации НЕ являются публичными HTTP endpoints.** Браузер не может задать цену, начислить себе баллы или вызвать settlement. Grant пока не выведен в админку/CLI; ADMIN-001 обязан получить actor из сессии, проверить свежую авторизацию, scope и лимит, затем вызвать эту команду. Reserve/settle/release должны вызываться только Jobs после проверки цены/доступа/доказательства результата. SDK worker также не получает произвольного доступа к ним. Генераций и настоящих платежей здесь нет.

Завершение ранее принятых обязательств возможно и после блокировки аккаунта, но только внутренней командой: это не разрешение пользователю выполнять новые генерации. Новый reserve при suspended/locked/deletion отвергается. Нулевой баланс не блокирует чтение своей истории.

## HTTP

`GET /api/v1/credits?limit=20` — собственный баланс и последние операции. Cookie проверяется существующим `AuthService.me`; пользователя нельзя выбирать query/body. `before` — исключающий sequence cursor для следующей страницы, `limit` 1…100. Ответ содержит `account_id`, `balance`, `entries`, `next_before`. Поля сотрудника, заявки и request hash не попадают в публичную запись.

Неизвестные/дублирующиеся query keys отвергаются. Guest/отозванная сессия —401; запрещённое состояние —403; неверная пагинация —422. В root действуют no-store/request-ID и безопасные ошибки. Для чтения не требуется доступ к GPU или provider. UI `/account/credits` ещё не создан; прежний баланс демо-студии не привязан к этому endpoint.

Composition root получает существующий resolver из `attach_accounts` и передаёт его в `attach_credits`. Вторая auth-служба/другой connection pool не создаются. Полный OpenAPI генерируется из приложения существующим инструментом:

```sh
python tools/export_contracts.py
python tools/export_contracts.py --check
```

Generated файл не редактируется вручную. При публикации экспорт выполнен из восстановленных и сверенных по Git blob SHA модулей приложения; прежняя часть схемы побайтно совпала с исходным OpenAPI. Окончательная проверка на lock-версиях выполняется в CI.

## Повторы, блокировки и сверка

Account locks берутся по возрастанию ID, затем wallet, затем reservation. Первый wallet создаётся только при записи под Account lock; GET ничего не начисляет/не создаёт. Для будущих cross-account admin команд этот порядок должен соблюдаться до удержания session lock; нельзя после блокировки actor брать target в произвольном порядке.

`operation_id` идемпотентен в пределах Account; сохраняется SHA256 канонического payload/version/kind/actor. Идентичный повтор возвращает оригинальную immutable receipt; другой payload —409. Проверки текущего права grant выполняются и при повторе. Terminal reservation нельзя повторно завершить новым operation ID; release не превращается в settle и наоборот. Request ID резерва и Case ID начисления имеют самостоятельную уникальность, поэтому новый operation ID не обходит запрет дублирования.

Projection, ledger, reservation и существующий account audit меняются в одной транзакции. PostgreSQL triggers запрещают UPDATE/DELETE/TRUNCATE ledger; DB owner способен отключить triggers — защиты от самого администратора БД не заявлено. Downgrade отказывается удалять непустой журнал. `reconcile` сравнивает projection, суммы проводок, число последовательных записей и сумму активных резервов; он лишь обнаруживает расхождения, не исправляет историю автоматически. Это не полноценный forensic-аудит всех after-snapshots.

## Проверки и дальнейшие условия

```sh
python -m pytest tests/test_credits.py tests/test_credits_http.py tests/test_credit_migration.py tests/test_credit_boundaries.py
```

Unit: реальные SQLAlchemy/SQLite, AuthService и сессии; не имитация результата `.me`. ASGI routes собраны с тем же resolver seam; полный production app/browser здесь отдельно не проверен. SQLite не доказывает PostgreSQL locking и execution triggers. Скрипт `tools/credit_acceptance.py` подготовлен для настоящего PG/HTTP и down/up в существующем CI; запуск требует test + IZO_CREDIT_ACCEPTANCE=isolated. Fixtures синтетические, private RUNNER_TEMP, не artifacts. Финальная штатная очистка уничтожает только CI-стенд; journal guards ради cleanup не отключаются.

Перед принятием: экспорт полного OpenAPI в целевом checkout, весь существующий pytest/build/browser CI, actual PostgreSQL races/trigger tests/restart, независимое review по возможности. Цены/внешние credentials/GPU/настройка main protection не входят в пакет.

Опорная семантика блокировок проверена по официальной документации PostgreSQL: https://www.postgresql.org/docs/current/explicit-locking.html . Это объясняет механизм, но не заменяет реальный тест нашего кода на PG.
