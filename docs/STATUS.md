# Фактическое состояние IZO ASA

## SEC-001 — зависимости web, 9 сентября 2026

База `21621137b51c938251fd35f909dddd2a07d67d21` (CREDIT-001, PR #6).
Отдельная ветка `security/npm-audit`, PR #8. Main, прежние ветки и рабочий сайт
не меняются. Ни merge, ни deployment, ни live AI/письма/платежи не выполнялись.

### Найдено и ограниченное исправление

Реальный npm audit исходного lock подтвердил high2: js-yaml4.3.1 и зависимый
@redocly/openapi-core1.34.19. Один исходный GHSA-2883-xcg3-v3hh / CVE-2026-84375,
не две независимые CVE. Цепочка — build/codegen через openapi-typescript7.10.1,
не обнаруженная ошибка Python-ledger. Подробности — apps/web/security/README.md.

Обновление родителя внутри разрешённого диапазона не дало исправления. Выбран
узкий override только для @redocly/openapi-core@1.34.19 на upstream js-yaml4.3.2.
Ни прямые версии web-пакетов, ни backend, ни миграции не изменены. Lock сгенерирован
npm на runner; сохранение старого формата записей не меняет его JSON-дерево.

Добавлен независимый read-only `Dependency Security / npm-audit`. Он не меняет
lock/исходники, не запускает package lifecycle scripts и не скрывает dev dependencies.
High/critical либо ошибка audit дают отказ; сохраняются отчёт и идентификация версии.
Четыре Node-regression tests проверяют actual parser, bounded merge budget,
обычный YAML и исходный OpenAPI. Четыре Python tests защищают свойства workflow.
Существующий Foundation CI с PG/restart сохранён без изменений.

### Доказательства и ограничения

На исходном lock audit-gate сработал отрицательно (run34292712936, high2).
Изолированный кандидат npm (run34292981711/artifact10082049192) дал audit total0,
маленький probe показал false→true для ограничения пустых merge sources на
4.3.1→4.3.2, обычный merge сохранился. Исходный диагностический run при этом
FAILURE: кандидат не подменял проверяемый checkout и не публиковался автоматически.

Локально выполнены четыре Python-проверки нового workflow и Node syntax check.
Полного checkout/Node24/npm registry/Docker в локальной среде нет; приёмка
окончательного source, build/browser/PostgreSQL выполняется в GitHub. Точный
итоговый SHA и все завершённые Checks фиксируются в PR #8, не переносятся с
изолированного candidate или предыдущего PR. Наличие тестов не равно их успеху.

Scope: до8 путей — manifest/lock, новый workflow, regression tests, предметный
security README, task scope и этот STATUS. Temporary candidate-generator удалён
из окончательного workflow. Нет переписывания приложения или общего master plan.
Самопроверка не независимое security review. Main protection остаётся отдельным gate.

## Ранее реализовано

Foundation: FastAPI/PostgreSQL/S3/Compose, schema readiness, OpenAPI, ограничения
кода и UI-прототип. AUTH-001: аккаунты, пароли, серверные сессии. Почтовая часть
AUTH-002: подтверждение/reset/change password с TEST-mail, без настоящей доставки.
CREDIT-001: wallet/ledger/reservations, grant/reserve/settle/release и owner-only
GET /api/v1/credits. PR #6/run34289604222:336 Python,220 browser и реальные PG/HTTP/
restart проверки прошли; найденный npm-сигнал стал отдельным SEC-001, не был скрыт.

Нет entitlements, рабочей admin-формы начисления, UI серверного баланса, durable jobs,
owner-scoped cloud gallery, live providers/credential resolver/local agent. Студия,
её баланс/галерея пока DEMO. Нынешний дизайн не принят. AUTH-002 не закрыт целиком:
смена email и linking/unlinking identities ещё впереди; настоящие Mini Apps/SMTP,
MFA/нагрузка/production secrets/backup restore также не объявляются выполненными.

## Продолжение

После успешного окончательного SEC-001 CI — ENTITLEMENT-001, затем ADMIN-001 по NEXT:
разрешённые модели/квоты и минимальная компенсация через авторизованную админку.
Не повторять foundation или переписывать существующую auth/credits без нового дефекта.
Ноль известных advisories не доказывает полной безопасности и не разрешает deploy.

NEXT — единственный план. IMPLEMENTED/TESTED/REVIEWED/PUSHED/MERGED/DEPLOYED
различаются; фактические coding-token расходы недоступны, процент экономии не заявлен.
