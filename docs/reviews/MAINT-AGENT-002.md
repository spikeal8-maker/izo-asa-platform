# MAINT-AGENT-002 · scope / self-review

## Цель
Сделать стоимость дальнейшей coding-agent разработки контролируемой по мере роста PRODUCT 0.2:
не только ограничивать размер отдельных файлов, но и initial context, local docs, scope и review-risk.

## До → после
До: giant-file hard guard работает, но near-limit файлы продолжают расти; route может давать десятки KB initial context;
local non-README docs обходят budget; domain AGENTS/README частично дублируются; recurring audit не является DoD.

После: бюджеты и audit закреплены в `MAINTAINABILITY.md` и machine-gates; текущий context debt сокращён;
каждый следующий package обязан доказать maintainability delta.

## Scope
Только governance/docs/tests/tools и структурное разбиение near-limit frontend/tests без изменения пользовательского поведения.
Product runtime, provider spend, billing, Catalog implementation и deploy вне scope.

## Обязательные проверки
- docs/state/checkpoint consistency;
- handwritten hard budgets + changed-file headroom;
- route/block initial context budgets;
- aggregate local-doc budget/stale metadata;
- workflow budget;
- scope class tests;
- existing Python/browser/container CI after any source split.

## Self-review вопросы
- Не увеличены ли лимиты вместо исправления структуры?
- Не превратился ли новый maintainability spec в ещё один roadmap/source of truth?
- Не вынесена ли нужная live-инструкция в history без короткой актуальной замены?
- Сохранились ли block owner/anchor/tests после split?
- Уменьшился ли фактический initial context, а не только размер отдельных файлов?
- Не изменилось ли product behavior из-за structural split?

Verdict: `IN_PROGRESS` до полного CI.
