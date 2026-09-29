# CHANGE-001 · проверка стоимости обычной правки

10 сентября 2026. Base f2e6f3a29410363412b22ee632e8e1d2e3921ac7. Это протокол
трёх выполненных подзадач, не новый план. Порядок следующих этапов остаётся в NEXT.

| Подзадача | Изменение | Производственные файлы | Профильные проверки |
|---|---|---|---|
| A · U-10/D-03 | Серверный резерв рядом с кнопкой подтверждения; две строки на телефоне, >=48px | Studio.tsx, studio.css | новый browser case в studio.spec.ts; старые submit/expiry/idempotency сохранены |
| B · S-10/S-11, PRODUCT §12 | Запрет модели/исполнителя/бюджета через существующую новую версию плана | **0**: новых backend-правил не потребовалось | 5 transactional cases, реальный PostgreSQL/HTTP через jobs acceptance |
| C · U-10/U-18 | Различать доказанный отказ до приёма и неизвестный исход по паре status/code | submission.ts, workspace-api.ts, Studio.tsx | новые protocol/browser cases; прежний lost-response case остаётся |

A и C редактируются последовательно; общий Studio.tsx не имеет двух пишущих владельцев.
Общий scope12 путей включает tests, один новый вспомогательный acceptance и этот отчёт.
Не менялись backend business-code, БД/migrations, dependencies, Docker, workflow, LICENSE.
Scope сравнивается с точным base, не с пустым HEAD. Снижение стоимости денег не заявляется.

## Измеренные проверки

Новые policy-tests:5 PASS за3.167s; расширенный профиль:114 PASS за21.903s.
Команда: `python -m pytest tests/test_change_access.py tests/test_jobs.py tests/test_jobs_http.py tests/test_entitlements.py tests/test_image_boundaries.py tests/test_web_boundaries.py`.
Локальный Node:27 assertions классификации/сообщений/transpile. Это не полный typecheck.
Исходный bug классификатора воспроизведён чтением прежнего literal allowlist: три
валидных отказа отсутствовали, проверка знакомого code не учитывала HTTP status.
Новые cases проверки права прошли на первом запуске без изменения CreditService/AuthService/JobService.

Локально нет Docker/locked web environment; полный CI не запускался после каждой строки.
Готовый PR получает существующие server/browser/PG/restart/security проверки. Точные
итоговые run/head, результаты и число повторов фиксируются в PR после выполнения.
Небольшой диагностический Node-скрипт сначала получил неверный options-аргумент;
исправлен только этот временный скрипт, не приложение. Повторного широкого scan не было.

## Ограничения измерения и следующий агент

Tokens/цена, исходная экономия относительно старого проекта и полный wall-time не
измерены. Три подзадачи выполнены одним агентом; это не независимый benchmark разных
моделей. Наблюдаемое доказательство — локализованные изменения/сохранённые границы,
а не обещание «в десять раз дешевле».

Для подписи/цены читать Studio + ближайший browser case. Для прав — существующие
entitlements commands + test_change_access, не всю админку. Для отказов — submission.ts
и workspace-api.ts; clear pending разрешён только при доказанном pre-admission отказе.
Новый provider с другими статусами требует отдельного подтверждённого контракта,
не добавления «любой4xx безопасен». Не копировать этот отчёт в AGENTS или следующий план.
