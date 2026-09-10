# Фактическое состояние IZO ASA

SETTINGS-001, 10 сентября 2026. Base `ba35c76a059351bbe698ac69cd58851dc803d0a5` / API-001 adapter technical pass; ветка `settings/typed-plan-lifecycle`, PR #19. Реализован ограниченный A-27/AD-08 lifecycle только для уже используемого basic PlanPolicy: typed preview, publish, history и rollback через существующие immutable `entitlement_revisions/default/changes`. Новая таблица настроек и миграция не создавались; Credits/Jobs/Media/provider business-code не переписывались. Zero/empty остаются deny, а включённая generation требует конечных обязательных лимитов. Точный финальный source SHA и результаты полного CI фиксируются в PR/Checks; MERGED/DEPLOYED — NO.

Текущая проверка исправляет два выявленных acceptance-дефекта без ослабления tests: временные base64-parts OpenAPI удаляются в пользу одного canonical `openapi.json.gz`, полученного из pinned FastAPI CI; `test_settings.py` регистрирует требуемый fixture явно. До зелёного exact-head Foundation CI SETTINGS-001 не считается технически принятым.

---

API-001 (подготовка), 10 сентября 2026. Base `8dd49ba1b5168ed5b9e363672497cca3e308d296` / CHANGE-001.
Добавлен первый внешний provider-adapter OpenRouter Images, но **live-вызов не выполнялся и не разрешён**: в репозитории нет реального ключа, выбранного владельцем model/budget и production-release. Точный опубликованный SHA/CI фиксируются в PR после push.

## API-001: что реализуется этим пакетом

- отдельный `providers/openrouter` с фиксированным HTTPS endpoint dedicated Images API; ответ только bounded base64 PNG/JPEG/WebP; response body/secret не логируются;
- provider credential передаётся только `openrouter-worker`; API/shared environment получает только не секретные model/price/resolution/connection параметры; provider выключен по умолчанию;
- quote/job сохраняют execution snapshot: adapter, connection, model, resolution, output format и продуктовую цену; изменение конфигурации делает ещё не принятую quote устаревшей;
- внешний job идёт в отдельный pool и не зависит от переключателя тестового renderer. Test worker его не claim-ит. Неоднозначный исход после network dispatch сохраняет резерв и переводит job в reconciliation без автоматического paid retry; сохранённый S3 result может быть финализирован без второго provider call;
- успешный fake-provider test проходит через общие Job/Credits/Media и сохраняет диагностические provider reference/usage cost. `usage.cost` не является биллингом IZO и не заменяет будущий USD spend-cap/reconciliation;
- новая migration `0009_provider_execution` добавляет только provider snapshot/receipt metadata. Старые миграции не переписываются.

Локально provider-contract и все предметные backend-наборы пройдены по отдельным группам; полный единовременный `pytest` в этой среде ограничен временем инструмента, поэтому окончательный общий статус берётся только из GitHub CI. OpenAPI snapshot обновлён из backend и хранится детерминированно в gzip (~5KB вместо прежних ~92KB JSON); web-скрипт распаковывает его только во временный node_modules cache при генерации TypeScript и удаляет после запуска. Это уменьшает diff/контекст coding-агентов без изменения схемы. Реальный OpenRouter запрос намеренно отсутствует из unit/CI.

## Граница API-001

Текущий пакет доказывает безопасный контракт и интеграцию без денег. Он **не закрывает требование NEXT о разрешённом real result** до выбора владельцем model/key/budget и отдельного live acceptance. Hard USD budget/каталог endpoint pricing и административное управление connections относятся к следующей части API-001/CATALOG-001; нельзя включать provider только потому, что env содержит ключ. Перед live acceptance нужен отдельный OpenRouter key с server-side spending limit и явно разрешённый малый бюджет владельца.

---

CHANGE-001, 10 сентября 2026. База — `f2e6f3a29410363412b22ee632e8e1d2e3921ac7`,
ветка image/server-workspace, PR #13. Новый пакет — change/targeted-maintenance.
Точный опубликованный head и окончательные результаты — Checks/комментарий PR.
Main, родительские ветки и рабочий сайт не меняются; MERGED/DEPLOYED — NO.

## Подтверждённая база, не повторная публикация старого пакета

При возобновлении обнаружено, что MEDIA-001, JOBS-001 и IMAGE-001 уже опубликованы.
Устаревший архив MEDIA повторно не применялся. Для source f2e6f3a… прочитан полный лог
Foundation CI34402090357/job102636174543:679 Python,360 viewport cases, все прежние
PostgreSQL/S3/перезапуск и реальный image-browser путь до/после restart — SUCCESS.
Dependency Security34402090422 и Review Source34402090426 — SUCCESS. Synthetic checkout
9780455507029ca600e4508401d8086f1ad12caa имеет tree3a57a9fb1b666c3c57acb21defa979ad29d7a662,
совпадающее с source tree. Скачанный source.tar.gz и231 blobs сверены локально.
В PR #13 записано подтверждение вместо устаревшего ожидания CI. Отдельный Review Source
в действующем коде сохранён; старое описание его удаления не соответствует этой версии.

## Изменения этого пакета

A — кнопка подтверждения показывает серверный резерв и перестраивается на телефоне.
Стабильное доступное имя/описание, touch-height48px; без локального расчёта цены,
глобального масштабирования, переустройства навигации или нового дизайна всей студии.

B — доказана смена доступа через существующую версию плана. После удаления capability
или executor, либо max_action_credits=0, старый ещё не принятый quote отвергается без
нового резерва/задания. Ранее принятые jobs сохраняют snapshot и читаемый результат.
Новая business-логика, коммерческие тарифы и админский редактор планов не добавлялись.
В existing PostgreSQL acceptance добавлен scoped сценарий на синтетическом аккаунте.

C — явный отказ по размеру/бюджету не оставляет студию навечно в неопределённом submit.
rejectedBeforeAdmission проверяет пару status/code. Незнакомый ответ/ошибка500/обрыв
сохраняют тот же operation ID; знакомый код внутри500 также не считается доказанным
отказом. Отдельное сообщение provider_unavailable подготовлено для протокола409,
но это не подключение настоящего AI. Локальные списания/refund/retry provider не добавлены.

## Проверки и воспроизводимость

Локально: 5 новых transactional policy tests — PASS, затем114 профильных tests — PASS,
без failures/errors/skips. Настоящие Accounts/Credits/Entitlements/Jobs с SQLite и fake S3;
отдельная PostgreSQL-проверка находится в существующем Compose gate. Node:27 assertions
классификатора/сообщений и транспиляцииTS — PASS, не полный TypeScript typecheck.
Python3.13.5/FastAPI0.128.2/Alembic1.18.4/Node22 отличаются от locked CI. Полного Docker
и браузеров локально нет; новые browser/PG сценарии не считаются пройденными до Checks.

Исходники восстановлены из git-tracked source artifact, upstream history локально нет.
Точное дерево и blobs проверены; локальный snapshot-коммит не выдаётся за remote source.
Scope проверяется по diff снимка и после публикации по GitHub compare от f2e6f3a….
Цена tokens и полное время работы агента не измерялись. Измерены только число путей,
команды и длительность локальных tests (см. [протокол CHANGE-001](reviews/CHANGE-001.md)); гарантий кратной экономии нет.

## Границы

Конечный scope12 путей, без изменений backend business-code, миграций, dependencies,
Docker-конфигурации, workflow, LICENSE или родительских веток. Три подзадачи выполнены
последовательно; документация дополняет текущие файлы, нового master plan нет.
Исходный IMAGE умеет истинный server job/галерею, но исполнитель только test.image.v1
с PNG TEST ONLY. Нет реальных AI/API-ключей/SMTP/GPU/payments. Визуал не принят владельцем,
OS scaling/настоящие Mini Apps и независимый review не объявлены проверенными.

После принятия CHANGE-001 — API-001 с явно выбранными provider/model/ключом/бюджетом.
До разрешения реальные вызовы не выполняются. Release/backup-restore/security review,
защита main, коммерческие квоты/retention и публичный scope остаются отдельными gates.
