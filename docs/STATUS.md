# IZO ASA · подтверждённое состояние

STATUS содержит **проверенные факты**, а не roadmap. Текущая изменяемая точка проекта живёт в
[CURRENT](CURRENT.md) и [PLAN](PLAN.json); exact-SHA evidence — в [CHECKPOINTS](CHECKPOINTS.json).
Исторический подробный статус до DOC-004 сохранён в `history/STATUS-before-DOC-004.md`.

## Последний frozen canonical checkpoint

`CHAT-V4-ADOPTION-001` принят как documentation/governance checkpoint от exact source:

- source SHA `811410e3cada4498161415bc279ce9a9f033ab6a`, PR #238;
- base `codex/chat-vision-001@2a2995ee47c8c369b512c1328f02d3eb662775a3`;
- Foundation CI `36497695762` — SUCCESS;
- Dependency Security `36497695888` — SUCCESS;
- Review Source `36497695795` — SUCCESS;
- runtime/product implementation в E0 не менялась;
- Chat P1 в E0 не начинался.

Freeze/checkpoint записан штатным project-state transition; authoritative evidence находится в
`docs/CHECKPOINTS.json`. Это не означает production deploy или разрешение на provider spend.

## Что уже реализовано в canonical lineage
Canonical lineage содержит backend boundaries для Accounts/Auth, Access, Credits, Entitlements,
Settings, Admin, Catalog, Media, Jobs, Guest, Chat и provider execution. Точная карта реализованного
и целевого состояния описана в [ARCHITECTURE](ARCHITECTURE.md).

Миграционная lineage существует от `0001_foundation` до `0015_chat_vision`. Наличие домена или
migration не означает автоматически product acceptance, production readiness или deploy.

## Исторические verified checkpoints

Старые API/DOC/LINEAGE checkpoints сохраняются как provenance и evidence, но **не являются текущим
technical baseline**. В частности, `api/fal-klein-001@faec39d6…` / PR #22, DOC-004 и DOC-004B —
исторические проверенные этапы, а не указание следующего package.

Параллельная OpenRouter lineage PR #15/#16/#17/#19/#20/#21 остаётся reference/provenance согласно
canonical project state; использовать её как continuation base без reconciliation нельзя.

## Что STATUS намеренно не хранит

Здесь не фиксируются active package, next package, рабочая ветка или mutable roadmap: эти значения
должны читаться только из `CURRENT.md` и `PLAN.json`, чтобы STATUS снова не становился источником drift.
