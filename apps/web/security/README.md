# SEC-001: безопасность зависимостей web

Дата: 9 сентября 2026. Следовать root/web AGENTS. Это предметный разбор issue #7,
не новая архитектура или второй roadmap. База — `21621137b51c938251fd35f909dddd2a07d67d21`.

## Причина и применимость

`openapi-typescript@7.10.1` → `@redocly/openapi-core@1.34.19` → `js-yaml@4.3.1`.
Audit исходного lock показал две high-записи, но один исходный advisory:
**GHSA-2883-xcg3-v3hh / CVE-2026-84375**, CPU amplification при повторном merge
пустых YAML mappings. Вторая запись — зависимый `@redocly/openapi-core`, не отдельная CVE.
Уязвимы js-yaml 4.0.0…4.3.1 и 3.0.0…3.15.1; upstream исправил 4.3.2 и 3.15.2.

В этом проекте цепочка относится к devDependencies и генерации типов из локального
`packages/contracts/openapi.json`. В финальный Caddy image копируется только dist,
не Node/node_modules. Найденный advisory сам по себе не доказывает атаки на API
или утечки баллов. Риск относится к обработке недоверенного YAML инструментарием;
dev/build-зависимости тоже проверяются. Не объявлять любой будущий импорт безопасным
только потому, что пакет сейчас помечен dev.

## Минимальное исправление

Обновление `@redocly/openapi-core` внутри разрешённого диапазона не изменило lock
и сохранило обе записи audit. Поэтому применён **version-scoped override** только
`@redocly/openapi-core@1.34.19 → js-yaml@4.3.2`. Это upstream patch того же major,
не переход на Redocly2/YAML5 и не глобальная принудительная замена всех парсеров.
Прямые зависимости, React/Vite, Python, Docker и приложение не обновляются.

Lock сгенерирован npm11.19.0/Node24.20.0 на изолированном GitHub runner через
`npm install --package-lock-only --ignore-scripts --no-audit --no-fund`.
Содержательно изменён ровно node_modules/js-yaml: version/resolved/integrity.
При публикации сохранён прежний однострочный формат package-записей; JSON-дерево
побайтного npm-артефакта и форматированной копии сравнено структурно и совпадает.
Значения versions/integrity не сочинялись вручную.

Удалять override можно отдельным небольшим изменением после проверки, что родитель
сам использует исправленный parser. Нельзя расширять его на любые версии Redocly,
использовать audit fix --force, omit=dev или отключать audit ради зелёного статуса.

## Проверки

Исходный read-only audit: run34292712936, source7e6bba1 — ожидаемый FAILURE/high2.
Невлияющее на checkout обновление родителя: run34292840303 — исправления не дало.
Изолированный scoped-кандидат: run34292981711, artifact10082049192 — audit total0;
маленький probe на четырёх пустых mappings: 4.3.1 не соблюдал budget2, 4.3.2 отверг
вход; обычный merge сохранил результат. Общий статус этого диагностического run
остаётся FAILURE, поскольку исходный checkout всё ещё содержал старый lock.
**Кандидат не считается окончательным source-CI**; финальные SHA/Checks — в PR #8.

Постоянный workflow `Dependency Security`, job `npm-audit`, использует read-only
токен, npm ci без lifecycle scripts, все dev/optional/peer зависимости, threshold high.
High/critical и ошибка реестра дают отказ; JSON/версия сохраняются в artifact.
Low/moderate не скрываются из отчёта, но этот gate не блокирует их автоматически.
Ноль advisories означает отсутствие известных совпадений в ответе на момент проверки,
не доказательство отсутствия всех уязвимостей и не scan Python/OS/images.

`dependencies.test.mjs`: реальное разрешение parser через codegen, affected-range
проверка всех копий, bounded regression для merge budget, совместимость обычного YAML
и чтения фактического OpenAPI. Нет нагрузочных payloads, внешней сети или ключей.
`tests/test_dependency_security.py` проверяет неизменность ограничений workflow.
Временный генератор candidate удалён из окончательного workflow; CI не меняет lock,
не коммитит код и не использует write-token.

В установленном Node24-окружении:
```sh
cd apps/web
npm audit --registry=https://registry.npmjs.org --include=dev --include=optional --include=peer --audit-level=high
node --test security/dependencies.test.mjs
npm run build
npm run test:e2e
```
`npm ci` нужен для нового checkout/изменённого lock; его нельзя повторять после каждой
правки кнопки. Полный Foundation CI и PG/restart остаются без ослабления. Чтобы сделать
`npm-audit` обязательным перед merge, настройка branch protection нужна отдельно;
сам workflow/AGENTS не отнимают у администратора право обхода. Merge/deploy не выполнены.

## Первичные источники

- Advisory автора: https://github.com/nodeca/js-yaml/security/advisories/GHSA-2883-xcg3-v3hh
- GitHub Reviewed: https://github.com/advisories/GHSA-2883-xcg3-v3hh
- Исправленный release: https://github.com/nodeca/js-yaml/releases/tag/4.3.2
- npm audit, exit codes, meta-vulnerabilities: https://docs.npmjs.com/cli/v11/commands/npm-audit/

Следующий продуктовый шаг остаётся ENTITLEMENT-001/ADMIN-001 в docs/NEXT.md.
Не повторять весь аудит проекта для новой точечной задачи.
