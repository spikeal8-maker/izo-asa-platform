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

## LINEAGE-001 · reconciliation facts

OpenRouter API-001 PR #15/#16/#17 и его descendants #19/#20/#21 разобраны как параллельная lineage.
Канонический runtime остаётся fal.ai. Provider-specific OpenRouter client/worker/runtime не переносится.
PR #19 сохраняется как typed Settings reference; PR #20 — как revision/audit/opaque-credential design reference;
PR #21 не принят как UI implementation из-за Foundation CI failure в catalog-only navigation tests.

Общий найденный gap — новые staff permissions без lifecycle их выдачи. Поэтому следующий canonical package —
ACCESS-001; затем re-author SETTINGS-002, CATALOG-002 и CATALOG-UI-002. Старые PR остаются reference-only.

## DOC-004 · verified checkpoint

Exact head `001edb9953d642f4d06453505809c20512f4b2b3` (`docs/agent-development-system`, PR #23) прошёл:

- Foundation CI `34637203126` — SUCCESS; 715 Python tests и 420 Playwright cases;
- PostgreSQL/S3/Compose restart и существующие browser acceptance markers — PASS;
- Dependency Security `34637203194` — SUCCESS;
- Review Source `34637203153` — SUCCESS.

Этот SHA считается frozen development checkpoint. Он не редактируется после PASS; следующие изменения идут
отдельной веткой от этого exact head. Merge/deploy/independent review по-прежнему не выполнены.

## DOC-004B · verified PR merge-tree checkpoint

Source head `fe47e208809b5950b08c7133ba922d7be5742d24` в PR #24 связан с успешными workflows:
Foundation CI `34647714472`, Dependency Security `34647714532`, Review Source `34647714613`.
Foundation проверил synthetic PR merge tree `b1c941966ea4fd53fd00322808e90adabbc28077`, где source head — один из родителей;
это **pr_merge_tree evidence**, не exact-source execution. В нём прошли 720 Python tests, 420 Playwright и
PostgreSQL/S3/Compose restart acceptance. Source head после этого не изменялся.
