# Web dependency security · локальная карта

Этот каталог содержит regression-проверки цепочки frontend/codegen dependencies. Он не является roadmap и
не хранит текущие SHA/PR. Исторический SEC-001 разбор сохранён в `docs/history/local-maps-before-DOC-004C/web-security.md`.

## Текущий контракт

`apps/web/package.json` содержит version-scoped override для `@redocly/openapi-core@1.34.19`, который фиксирует
`js-yaml` на исправленной версии `4.3.2`. Это build/dev dependency codegen, а не runtime-библиотека Caddy bundle.
Override нельзя расширять глобально или удалять без повторной dependency/security проверки.

Проверки:

```sh
cd apps/web
npm audit --registry=https://registry.npmjs.org --include=dev --include=optional --include=peer --audit-level=high
node --test security/dependencies.test.mjs
npm run build
```

Foundation browser suite и `Dependency Security` workflow остаются отдельными gates. `npm audit` не доказывает
отсутствие всех уязвимостей Python/OS/images; он проверяет известные advisories npm dependency graph.
