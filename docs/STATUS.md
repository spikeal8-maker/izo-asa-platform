# Фактическое состояние IZO ASA

## ENTITLEMENT-001 · 9 сентября 2026

База fd765c5002250ed0d12f317170323d7c841b9e4b (SEC-001, PR #8).
Повторная отправка локального пакета через GitHub разрешена; ветка entitlements/server-policy.
Первая попытка была остановлена инструментом, после запроса владельца запись повторена.
Архив, патч и все 21 исходных файла сверены с manifest SHA256/Git blob SHA.
Точный опубликованный commit/PR и завершённый CI фиксируются в Checks/описании PR;
успех PostgreSQL нельзя переносить с SEC-001. Main и предыдущие ветки не меняются.
Merge/deploy, реальные AI/SMTP/платежи/GPU и production-данные не входят в этап.

### Реализованный серверный блок

Новая миграция0005_entitlements (parent0004_credits): plan revisions, default pointer,
account assignments и immutable change history. Publish/set-default/assign/clear —
внутренние команды с active plans.write, expectedVersion, идемпотентной receipt и audit.
Пустой default означает configured=false, не unlimited бесплатный доступ.
GET /api/v1/entitlements читает только свой план через существующую session в одной
транзакции; чужой owner/query, revoked session и публичные mutations запрещены.

Начало/истечение назначения выбираются на сервере. Истечение возвращает текущий basic,
не меняя баллы/permissions/старые snapshots. Strict finite quota/capability/executor/
image-size/input/budget policy. Неизвестный usage отвергается. Цена и значения реальных
тарифов не назначены; тестовые значения не объявляются production defaults.

assess_image использует реальный Credits available, но является preflight:
admission_reserved=false. JOBS/MEDIA ещё не считают/резервируют настоящие ресурсы,
поэтому это НЕ законченный механизм конкурентного допуска AI-заданий. Положительный
preflight не разрешает worker dispatch. Следующие домены обязаны повторно проверить
свежий server-owned usage под owner lock и атомарно создать allocations/credit hold/job.

Подробная граница/команды — apps/api/izo/entitlements/README.md, короткая карта — AGENTS.md
рядом. Нет новой авторизации, второго ledger, generic settings engine и UI планов.

### Проверки и scope

Локально прошли 80 новых SQLite/ASGI/schema/architecture checks. Совместно с
103 существующими CREDIT-001 checks — 183 PASS. Это только восстановленный
профильный набор предыдущей подготовки, не новый полный suite репозитория.
PostgreSQL/HTTP/race/restart и полный набор новой опубликованной версии проверяются
в GitHub; итог подтверждается по завершённым Checks, не наличию сценария.
Полного git clone/Docker в локальной среде нет; исходные импорты
получены через connector и сверены по Git blob SHA, новые HTTP tests используют
настоящий AuthService. Локальные FastAPI/Alembic отличаются от lock.

OpenAPI генерируется штатным tools/export_contracts.py. После удаления нового endpoint
и трёх DTO старая часть совпала с blob bbf03e6e3196cf095fabf5479c3b0ca86e8265a7.
Не выполненные тесты не объявляются прошедшими. PG acceptance проверяет version races,
один эффект replay, immutable history, собственный HTTP, persistence и expiry с
управляемыми часами после настоящего restart; не реальный час ожидания.

Scope: 21 путь при пределе24. Existing app получает attach route; новая migration,
сервис/политика/facade/тесты/docs/schema. Workflow добавляет before/after и private
cleanup вокруг прежнего restart; все старые функциональные и npm security gates
сохраняются. Auth/Credits internals, UI, зависимости, Docker, LICENSE не меняются.
Нет полного checkout — локальный check_change не объявлен выполненным; remote compare
должен подтвердить пути. Самопроверка не независимый security review.

## Ранее реализовано и ограничения продукта

Foundation/FastAPI/PostgreSQL/S3/Compose; AUTH-001 и почтовая часть AUTH-002 с TEST-mail;
CREDIT-001: ledger/hold/grant/reserve/settle/release и owner-only read API.
SEC-001: scoped js-yaml patch и независимый npm audit gate. Source fd765c5 был проверен
run34293879081 (340 Python,220 browser,PG/HTTP/restart) и run34293879085 (audit и4 Node
regressions). Ноль известных advisories не является полной оценкой безопасности.

Нет рабочей admin-формы начисления, UI серверного баланса/планов, Jobs/Media allocation,
облачной пользовательской галереи, live adapters/credential resolver/GPU agent.
Студия и её баланс/галерея — DEMO; дизайн не принят. AUTH-002 не закрыт целиком:
смена email/linking, настоящие Telegram/MAX/SMTP, MFA/нагрузка/backup restore и
production secrets ещё впереди. Branch protection/обязательный независимый review
не настроены этим пакетом. Старый сайт и данные не затронуты.

Следующий ограниченный шаг после технической приёмки — ADMIN-001: пользователь,
серверный баланс и одно начисление компенсации с правами/audit на существующем ядре.
NEXT — единственный план; никаких новых master plans. IMPLEMENTED/TESTED/REVIEWED/
PUSHED/MERGED/DEPLOYED различаются. Фактических coding-token расходов нет, процент
экономии не заявляется.
