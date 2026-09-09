# Entitlements: ограниченная область

Наследует root/backend AGENTS. Этот модуль не создаёт новый Account/Credits/Jobs.
- Поля и команды: schemas.py; чистые отказы: policy.py.
- Выбор версии/сроки/изменения: service.py, repository.py, tables.py.
- Identity/permissions: только accounts/entitlement_access.py и существующая session.
- Public GET: routes.py; нет HTTP назначения плана или доверенного client usage.

Для небольшой правки читать её файл, README-контракт и ближайший test, не все тарифы/UI.
Профиль: `python -m pytest tests/test_entitlements.py tests/test_entitlements_http.py
 tests/test_entitlement_migration.py tests/test_entitlement_boundaries.py` (одной командой).
После изменения public DTO — `python tools/export_contracts.py`; перед приёмкой полный CI.

Не менять старые миграции, CreditService/пароли, lockfiles или визуал заодно.
План не staff-role, нулевой лимит не unlimited, истечение не списывает баллы.
Изменения выполняются во внешней транзакции, с expectedVersion/replay и audit.
Блокировать все затронутые Accounts по UUID ДО session/default/wallet. Будущий
ADMIN не должен держать actor lock и затем брать target в обратном порядке.

assess_image — только preflight с admission_reserved=false. Успех не право вызвать
provider: JOBS/MEDIA обязаны повторно проверить актуальные counters и атомарно
создать allocations/reservation/job. Missing/stale/cross-account usage — отказ.
Не брать usage/provider_available из браузера и не считать пустые таблицы отсутствующих
Jobs/Media нулевой загрузкой. Secrets и настоящие API не входят в этот scope.
