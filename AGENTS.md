# IZO ASA · обязательные правила coding-агента

Цель: безопасная правка с минимальным достаточным контекстом.

## Старт

1. Прочитать `docs/CURRENT.md`; выполнить `python tools/project_state.py verify`.
2. Найти точный block/route через `tools/context.py`; при ambiguity не угадывать.
3. Зафиксировать goal, base, finite scope, non-goals, risk и nearest tests.
4. Package history читать только точечно: `project_state.py show-package <ID>`.
   `PACKAGES.json`, CHECKPOINTS, reviews и history — не default context.

## Неподвижные границы

- Account / Credits / Jobs / Media — shared owners; второй auth/ledger/gallery запрещён.
- Backend владеет identity, permissions, ownership, price и provider/storage authority.
- Unknown paid outcome сначала reconcile; blind paid retry запрещён.
- Unit/UI не используют production secrets/network/data; integration изолирован.
- Расходы, платежи, DNS, merge/deploy/release и owner-only actions требуют отдельного разрешения.

## Рабочий цикл

`LOCATE → SOURCE_AUDIT → SCOPE → acceptance case → minimal change → TARGETED TEST → SELF_REVIEW → required CI → FREEZE`.

Не ослаблять tests/limits и не расширять scope ради PASS. Budgets, Source-First, audit cadence и risk review —
`docs/MAINTAINABILITY.md`.
## Git/state safety

Нельзя `reset --hard`, force-push, чистить чужой WIP, auto-merge или auto-deploy.
PLAN/PACKAGES/CURRENT/CHECKPOINTS меняет только repository state workflow.
Следующий package не стартует вручную; `complete` — terminal status и не понижается.

## Multi-agent и review

Controller/subagent contract, one-writer isolation, delegation, reviewer separation и STOP conditions —
`docs/DEVELOPMENT.md`. Internal review не заменяет required GitHub review/owner waiver.

## SELF_REVIEW и handoff

Проверить: исходную задачу, минимальность diff, ownership/security/idempotency/cost/privacy,
risk-specific error/race/restart cases, budgets, docs/routes и отсутствие ослабленных gates.
Verdict: `PASS | FIX_REQUIRED | ESCALATE`.

Documentation ownership — `docs/DOCS_SYSTEM.md`; новый MASTER_PLAN/NOW/ROADMAP запрещён.
Handoff: package, branch/base, diff, tests/CI, риски и один следующий шаг; без reasoning/больших логов.
