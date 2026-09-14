# MAINT-AGENT-002 · self-review

## Цель
Сделать стоимость дальнейшей coding-agent разработки контролируемой по мере роста PRODUCT 0.2:
ограничивать не только отдельные файлы, но и initial context, local docs, scope и review-risk.

## До → после
До:
- hard giant-file guard существовал, но near-limit файлы могли расти до самого hard-limit;
- 13 generic routes давали >18 KB initial context;
- Accounts/Jobs live-docs превышали aggregate budget, а `accounts/EMAIL.md` содержал package-history;
- `test_accounts.py` и `test_entitlements.py` были на 97–99% auxiliary hard-limit;
- scope мог формально доходить до 100 файлов;
- domain-specific guest routing накапливался как `if` в `context.py`;
- independent review high-risk пакетов был только текстовым правилом.

После:
- production hard budget 12 KB/300 lines, auxiliary 16 KB/350 lines дополнен changed-file headroom guard;
- default/block/route context и aggregate local-doc budgets проверяются машинно;
- дорогие generic routes сокращены до owner docs/platform rules, source перенесён в `expand_if_needed`;
- stale Accounts email history заменена короткой live note, Jobs duplicate AGENTS удалён;
- Accounts/Entitlements tests разделены по responsibility с общими support fixtures;
- scope classes: tiny≤8, normal≤20, cross_domain≤40 + reason/domains/non_goals;
- risk=high требует `independent_review_required=true`;
- `begin-next` fail-closed требует exact-source PR marker `INDEPENDENT_REVIEW PASS` до создания следующей ветки;
- domain-specific routing signals перенесены в data rules; router/docs checker поддерживают будущие shard indexes;
- полный repository agent-economy audit обязателен после каждых 5 product packages.

## Scope
Только governance/docs/tests/tools и структурная тестовая декомпозиция. Product behavior, provider spend, billing,
Catalog implementation, business schema/data и deploy не менялись. Текущий cross_domain scope ограничен 40 файлами.

## Проверенные риски self-review
- **Лимиты не повышались.** Первый новый CI намеренно упал на существующем context/doc debt; исправлялась структура.
- **Guard проверяет сам себя.** После shard-validator `tools/check_docs.py` вырос выше 80% auxiliary hard-limit; headroom gate остановил PR. Вместо исключения validation logic вынесена в отдельный `tools/docs_context.py`.
- **Routing correctness:** semantic guest preferences теперь data-driven; routing corpus остаётся обязательным gate.
- **Sharding:** current maps физически не раздроблены без необходимости, но loader/validator готовы к shards и запрещают duplicate keys.
- **Review evidence:** PASS старого SHA не подходит новому commit; high-risk transition проверяется до branch creation.
- **Test split:** один canonical core-test остаётся в старом имени, support fixtures не копируются между файлами.
- **Frontend:** `Studio.tsx` остаётся near-limit legacy source, но headroom gate запрещает его рост. Корректный component split должен идти вместе с FRONTEND package и обновлением BLOCK_MAP owners; фиктивный split ради метрики в этом maintenance package отклонён.
- **Product runtime:** API/domain/web behavior не изменялись этим package.

## Acceptance перед freeze
- `python tools/check_docs.py` / docs-system tests;
- full Python/unit/architecture including routing corpus, scope/risk, shard loader and review evidence tests;
- browser matrix;
- PostgreSQL/S3/container/restart acceptance;
- Dependency Security + Review Source;
- changed files ≤ current cross_domain max_files;
- финальный source после green CI не редактируется.

SELF_REVIEW: **PASS**. Финальный technical verdict зависит от полного CI на последнем source head.
