# DOC-004B · Maintenance Precision — SELF_REVIEW

Base/frozen checkpoint: `001edb9953d642f4d06453505809c20512f4b2b3` (`docs/agent-development-system`).
Working branch: `docs/maintenance-precision`. Runtime product code не меняется.

## Acceptance

Цель — закрыть четыре дефекта DOC-004: неоднозначный branch-from, feature-level вместо block-level контекста,
слишком уверенный lexical router и semantic drift локальных README.

Реализовано:

- PLAN разделяет `runtime_base`, frozen `branch_from` и `working_branch`;
- CURRENT генерируется из PLAN, а не редактируется как второй source of truth;
- `BLOCK_MAP.json` содержит 16 стабильных owner/symbol/anchor locators без line numbers;
- router сначала ищет block, затем route; близкие кандидаты дают `AMBIGUOUS`, слабые — `NOT RESOLVED`;
- routing corpus расширен до 30 normal/voice/ambiguous/unsupported запросов;
- `project_state.py` проверяет checkout и задаёт безопасный start-next-package переход;
- frozen checkpoint после CI не получает status commit; переход выполняет новая ветка;
- Jobs README сокращён и синхронизирован с существующим fal lifecycle;
- checker валидирует anchors, route/local-map coverage, generated CURRENT и UTF-8.

## Дефекты, найденные self-review до публикации

1. `backend` давал очки любому backend-block и делал `csrf login backend` неоднозначным. Исправлено: это только intent bonus.
2. Общее слово `job` тянуло domain-запрос к submit/cancel blocks. Исправлено: exact `submit job` остаётся сильным, общий job — route-level.
3. Unsupported `кнопка удалить работу` ошибочно попадала в download block по слову «работу». Добавлен minimum block confidence; теперь safe unresolved.
4. Pretty-print PLAN увеличил его примерно до 340 строк. Добавлен compact serializer: около 100 строк / <10KB.
5. Generated PLAN/CURRENT на Windows давали CRLF normalization warnings. Generator переведён на явные UTF-8 bytes/LF.
6. `jobs/README.md` противоречил соседнему `jobs/AGENTS.md`, утверждая отсутствие внешнего AI lifecycle. README заменён provider-neutral картой.
7. Уточнено правило PR: body/comment — evidence snapshot; после freeze source SHA не редактируется ради обновления статуса.

## Измерение контекста

До block locator типовая Gallery-правка тянула примерно 33KB документов/feature files. Новый locator для
`сделай кнопку Скачать шире` выдаёт `AssetPage.tsx → Work.download → async function download()` и стартовые
AGENTS/CURRENT/local-map примерно 10KB; source читается диапазоном вокруг anchor, а не целиком.

## Проверки до push

- `python tools/check_docs.py` — PASS: 16 blocks / 15 routes;
- `python tools/project_state.py verify` — PASS;
- routing corpus — 30/30 expected resolve/ambiguous/unresolved;
- docs/project-state + change-scope + existing web/image boundaries — 42/42 PASS на Windows с `PYTHONUTF8=1`;
- `git diff --check` — PASS.
- Локальный full pytest не считается gate: baseline `test_acceptance_regressions` падает до project logic, потому что
  Windows asyncio `socket.socketpair()` перехватывается существующим unit network-ban fixture. Этот fixture не ослаблялся;
  exact Linux GitHub CI остаётся финальной полной проверкой.

Verdict: **SELF_REVIEW PASS · FULL GITHUB CI PENDING**.
