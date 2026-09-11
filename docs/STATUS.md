# IZO ASA · подтверждённое состояние

STATUS содержит **факты**, а не roadmap. Текущая точка/active package — [CURRENT](CURRENT.md),
машинный план — [PLAN](PLAN.json). Подробная история до DOC-004 сохранена в
`history/STATUS-before-DOC-004.md` и package reports в `reviews/`.

## Каноническая техническая база

Baseline: `api/fal-klein-001` @ `faec39d6ae0b4f035ef0f86114494789acde3b46`, PR #22.
PR Draft; merge/deploy/live fal acceptance — **NO**.

API-001 на этом head технически проверен GitHub Actions:

- Foundation CI `34575946516` — SUCCESS;
- Python 3.13.15 — 710 passed;
- OpenAPI consistency и TypeScript/Vite build — PASS;
- Playwright matrix — 420 passed;
- PostgreSQL 17 + migration `0009_provider_calls` — PASS;
- S3/SeaweedFS и Compose restart/persistence — PASS;
- прежние AUTH/EMAIL/CREDIT/ENTITLEMENT/ADMIN/MEDIA/JOBS/IMAGE acceptance — PASS;
- Dependency Security `34575946552` — SUCCESS;
- Review Source `34575946535` — SUCCESS.

Это доказывает технический contract fal-adapter и существующего server flow. Реального `IZO_FAL_KEY`,
real fal request/provider billing, production data, independent review, merge или deploy не было.

## Обнаруженная process-проблема

В репозитории существует параллельная OpenRouter-линия API-001 (#15/#16/#17), поверх которой созданы
SETTINGS-001 (#19) и CATALOG-001 (#20/#21). Она не является канонической после выбора fal.ai, но содержит
потенциально полезный provider-neutral код. Автоматически продолжать её запрещено до LINEAGE-001.

Это расхождение и устаревшие mutable фразы в INDEX/NEXT/AGENTS стали причиной DOC-004.

## DOC-004 · verified checkpoint

Exact head `001edb9953d642f4d06453505809c20512f4b2b3` (`docs/agent-development-system`, PR #23) прошёл:

- Foundation CI `34637203126` — SUCCESS; 715 Python tests и 420 Playwright cases;
- PostgreSQL/S3/Compose restart и существующие browser acceptance markers — PASS;
- Dependency Security `34637203194` — SUCCESS;
- Review Source `34637203153` — SUCCESS.

Этот SHA считается frozen development checkpoint. Он не редактируется после PASS; следующие изменения идут
отдельной веткой от этого exact head. Merge/deploy/independent review по-прежнему не выполнены.
