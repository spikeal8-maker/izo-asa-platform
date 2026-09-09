# ENTITLEMENT-001 · версии плана и серверная политика

9 сентября 2026. PRODUCT §12, A-06/A-07, S-09…S-17 и image-budget portion S-21.
База fd765c5002250ed0d12f317170323d7c841b9e4b, продолжение Accounts/Credits и SEC-001.

## Реализованный объём

Миграция0005_entitlements создаёт immutable revisions, единственный default pointer,
текущие assignments и append-only changes. Начальный pointer пуст: configured=false,
а не бесплатный план без квот. Один опубликованный basic revision назначается default
внутренней авторизованной командой. Расширенные/custom назначения поддерживают
начало, истечение, смену/очистку с version conflict. Коммерческие цены не придуманы.
Нет generic admin editor, checkout, подписки, UI тарифов или бонуса регистрации.

`GET /api/v1/entitlements` возвращает только текущему аккаунту effective revision,
policy/hash, базовую/индивидуальную причину выбора, version, состояние назначения и
ближайшую временную границу. Существующая cookie проверяется вместе с чтением policy
в одной транзакции. Query выбора owner/role/плана отвергается. Session expired/revoked
не работает. При security lock/delete обычный доступ запрещён; generation_suspended
может прочитать план, но не получить положительный generation preflight.

Public view не содержит паролей, keys, audit reasons или внутренних actor IDs.
Нет публичных POST assign/publish/default/assess. Публикация/назначение/смена default —
внутренние server commands; actor MUST быть получен доверенным session/operator code.
Проверяются active + plans.write и отсутствие expiry permission. Только basic может
стать default. В текущей Accounts модели grant глобален; более узкое делегирование
и свежая staff-auth добавляются в ADMIN/ACCESS, не объявлены готовыми здесь.

## Инварианты

Одна assignment не складывается с другим планом. До starts_at используется текущий
basic, начиная со starts_at и строго до expires_at — assignment, с expires_at снова
актуальный basic. Если default не настроен, fallback закрыт. Просроченная assignment
не удаляется чтением. Ранее полученный snapshot содержит неизменяемую policy/hash;
будущий job должен сохранить его, а не читать постоянно изменяемый план вместо снимка.
План не переписывает balance, не отнимает архив и не назначает staff permissions.

Policy строго типизирована, extra/boolean-as-number/fraction/negative отвергаются.
Нулевые квоты и пустые allowlists запрещают соответствующую операцию. В коде есть
конечные технические upper bounds, но нет утверждённых чисел коммерческих тарифов.
Capability ID соответствует действующему contracts.Capability; plan не регистрирует
модель и не обещает, что её режимы поддержаны. Runtime поддержка проверяется отдельно.

Каждая команда получает operation_id/reason и работает в savepoint внешней транзакции.
Одинаковый command возвращает исходную receipt без второй записи. Другие аргументы
с прежним ключом — conflict. Ожидаемая версия обязательна: два редактора не затирают
друг друга. Assignment, change receipt и account audit откатываются вместе при ошибке.
PostgreSQL запрещает обычные UPDATE/DELETE/TRUNCATE revisions/changes. Это не защита
от администратора самой БД. Populated downgrade запрещён, история не чистится каскадом.

Порядок locks: все затронутые Accounts по UUID; session при необходимости; default
pointer; затем existing Credits wallet. Ревизия неизменяема. Чтение default использует
shared lock; его изменение — exclusive row lock. Нельзя запускать внутри транзакции
долгую генерацию/сетевой вызов. Нет in-memory прав на пользователя.

## Граница preflight — не готовый quota allocator

`assess_image(conn, trusted_account_id, demand, runtime, usage)` принимает только
серверные объекты. Проверяет status/verification, feature gate, plan capability/executor,
runtime support/availability, image size, inputs, cost cap, active/window counters,
committed+reserved storage+output bound и реальный available баланс через Credits.
Приоритет отказов детерминирован. Local outage не изменяет отдельную API-проверку.

UsageSnapshot обязан иметь тот же account, timestamp и rate window. Отсутствующее,
устаревшее или чужое usage даёт usage_unavailable, не нули. Специально нет endpoint,
позволяющего клиенту прислать «usage=0» или «provider_available=true».

**Даже allowed=true возвращает admission_reserved=false.** Это проверка политики,
не разрешение worker и не резерв ресурса. JOBS/MEDIA пока отсутствуют и не могут
выдать настоящие counters: до их реализации не заявляется ограничение конкурентных
AI-заданий на работающем сайте. В будущем вызывающий сервис держит owner lock,
читает актуальное usage и в одной внешней транзакции создаёт quota allocation,
Credits reserve и job. Нельзя перенести этот snapshot через сетевой вызов и после
него считать лимит гарантированным. Provider side effects — только после commit.

Сейчас demand ограничен image-сценарием. Video/audio/3D/chat quantitative consumers,
publishing, подсчёт хранилища и sliding-window admission реализуются профильными
пакетами. Поля/тесты не являются реализацией будущих функций. Этот код не меняет
демонстрационный баланс/галерею frontend.

## Проверки и команды

```sh
python -m pytest tests/test_entitlements.py tests/test_entitlements_http.py tests/test_entitlement_migration.py tests/test_entitlement_boundaries.py
python tools/export_contracts.py --check
```

Локально — SQLite/ASGI с настоящим AuthService; сеть запрещена tests/conftest.
Реальные PG races/triggers/restart — tools/entitlement_acceptance.py before/after,
добавленные в existing CI вокруг Compose down/up. Guard требует environment=test,
pg_host=postgres, pg_database=izo, IZO_ENTITLEMENT_ACCEPTANCE=isolated. Cookies/state —
только закрытый RUNNER_TEMP, не лог/артефакт. History guards для очистки не отключаются:
одноразовые CI-volumes уничтожаются прежней явной финальной процедурой.

Точные SHA, завершённый CI и пределы результата — PR/Checks. Самопроверка не внешний
audit. Следующий продуктовый шаг — ADMIN-001, а не повторное проектирование базы.

Опорная семантика PG locks: https://www.postgresql.org/docs/current/explicit-locking.html
Строгая валидация и границы frozen models: https://docs.pydantic.dev/latest/concepts/models/
