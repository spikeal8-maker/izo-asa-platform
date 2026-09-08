# Фактическое состояние IZO ASA

Срез: 8 сентября 2026. Требования не равны готовым функциям. Ветка `foundation/initial-platform`, [PR #1](https://github.com/spikeal8-maker/izo-asa-platform/pull/1). Main и рабочий сайт не обновлены; merge/deploy не выполнялись.

## 1. F0-ACCEPT: технический разбор и ограниченные исправления

Проверенная исходная версия — `a208ec3e42c9306e56dfe8d73f19bcf382553c84`. Пользователь поручил разработку и проверку следующего этапа. Выполнен отдельный технический проход по основанию и воспроизведение дефектов; это самопроверка с regression tests, **не независимое внешнее review**.

Исправления в этом пакете:
- F0-R1: readiness больше не сравнивает БД с навечно зашитой `0001`. Читается единственный Alembic head из поставленного кода; БД с другой/пустой/несколькими revisions отвергается. Проверка БД read-only и ограничена timeout. Никаких миграций при импорте или health-запросе.
- F0-R2: добавлен отсутствовавший `migrations/script.py.mako`. Создание следующей revision через Alembic проверяется в временном каталоге без подключения БД. Существующая migration 0001 не менялась.
- F0-R3: необработанное исключение до начала HTTP-ответа даёт безопасный JSON 500, request ID, no-store/nosniff и структурированное событие ошибки без текста exception/query. Ожидаемые HTTP errors сохраняют свой статус.
- F0-R4: конфигурация отвергает некорректные порты/встроенные credentials/неподходящие S3 URLs; печатная диагностика ValidationError не раскрывает вход. `ValidationError.errors()` без `include_input=False` по-прежнему нельзя публиковать: это не универсальный redactor.

Изменён только этот STATUS, три существующих backend-файла, добавлен шаблон миграций и два файла тестов. UI/дизайн, contracts/generation policy, БД/0001, Docker, workflow, зависимости, LICENSE и реальные ключи не изменялись.

## 2. Проверки и ограничения evidence

Локально извлечённые через GitHub source-файлы сверены с Git blob SHAs исходного коммита. Это не полный git clone: прямой сетевой доступ из среды отсутствует. На исходном коде первоначальные regression cases дали **9 FAIL / 4 PASS**: восемь отказов в tests/test_acceptance_regressions.py и один в test_migration_workflow.py. После исправления и расширения — **24 PASS** в двух новых файлах; сеть запрещена существующим conftest.

Локальный Python 3.13.5, FastAPI 0.128.2, Pydantic 2.13.4 и Alembic 1.18.4 отличаются от закреплённого GitHub-окружения. Полный suite, точные зависимости, browser и Docker проверяются в GitHub. Здесь Docker отсутствует; локального контейнерного запуска не было. Статус окончательного нового SHA фиксируется в Checks/описании PR после фактического завершения, не переносится с исходной версии.

Исходный [run 34212525390](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/34212525390), job `102016611508`, `a208ec3…` повторно прочитан: SUCCESS всех предусмотренных проверок. Исторический baseline `5f8f318…`, run `34158092764`: 107 unit/architecture и 30 Chromium shell cases. Число будущего полного suite не выводится из арифметики, пока не прочитан лог нового run.

Новые тесты подтверждают создание/чтение следующей packaged revision, отказ неоднозначной/неподходящей БД, safe diagnostics, exception isolation для HTTP и сохранение 4xx-кодов. DB transport в unit fake; реальные PostgreSQL/S3 остаются отдельным шагом Compose CI. Cache metadata относится к неизменяемому release; после добавления migration процесс перезапускается.

Наличие перечисленных положительных проверок не доказывает streaming/background error handling, полную безопасность секретов, ownership ещё отсутствующих endpoints или готовность production. QHD/4K и реальные Mini Apps пока требования; прежние shell cases их не заменяют. Volumes persistence не является backup restore.

## 3. Существующая реализация

FastAPI factory/liveness/readiness, PostgreSQL/Alembic baseline, приватный S3 boundary, React shell/nav/themes/dialog, JobSpec/Capability/AssetRef и чистые routing/state rules, OpenAPI export/generated types, dependency locks и изолированный CI.

Нет регистрации/session/recovery, работающих permissions/entitlements/ledger/admin, durable worker, owner-scoped uploads, live providers/credential resolver/local agent, функциональных gallery/feed/chat/video/audio/3D, оплаты и production release/restore. Технический shell не принят как дизайн.

Документация 0.2 сохранена: U45/D14 в PRODUCT; A30/AD10/S66 в ADMIN; единственный план NEXT. Маршруты, профили планов и DRAFT defaults — предлагаемые контракты, не согласованные коммерческие цены. F0-ACCEPT не меняет продуктовый scope и не начинает реализацию всего реестра.

## 4. Решение для продолжения и незакрытые gates

После успешного полного CI исправленного SHA техническое основание допускает дальнейшую **изолированную разработку UX-001 и AUTH-001**. Не требуется новый общий план или ещё одна повторная проверка того же основания без новых данных. Это не разрешение merge/deploy и не утверждение дизайна.

При этом проверке GitHub `/branches/main` снова вернул `protected:false`, main=`93d9417…`. Доступный connector не предоставляет запись branch protection/administration; поиск дополнительных подключений не дал подходящего средства. Правила защиты и независимое review остаются отдельным организационным gate принятия в main; их нельзя объявить настроенными по файлам AGENTS/CODEOWNERS. Продолжение в ограниченной feature-ветке не требует выдачи production-доступа.

Неблокирующие для прототипа задачи: расширенные QHD/4K/HiDPI tests и дизайн — UX-001; полноценные runtime-contract validators/user permissions — соответствующие feature-пакеты; image digests, production secrets/egress, safe telemetry/streaming, backup/restore и workload baseline — до своих публичных функций. Smoke tool сейчас использует стандартный dev-порт 8080; поддержку изменяемого порта нужно синхронизировать до инструкции с другим портом.

Следующий пользовательский результат — одна новая интерактивная концепция студии/результата/галереи по issue #2, без настоящих AI-вызовов. Затем вход и первый законченный image flow по NEXT. Список цен/квот/provider/budget/retention/LICENSE и публичный scope остаются решениями соответствующих этапов.

## 5. Как обновлять

IMPLEMENTED / TESTED / REVIEWED / PUSHED / MERGED / DEPLOYED / OPERATIONALLY VERIFIED независимы. Для evidence указывать SHA, среду и реальный результат. [INDEX](INDEX.md) — карта документов; [NEXT](NEXT.md) — порядок работ. Само наличие этого документа не заменяет прочтение конечных Checks PR.
