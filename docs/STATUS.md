# IZO ASA · подтверждённое состояние

STATUS содержит **проверенные факты**, а не roadmap. Текущая изменяемая точка проекта живёт в
[CURRENT](CURRENT.md) и [PLAN](PLAN.json); exact-SHA evidence — в [CHECKPOINTS](CHECKPOINTS.json).
Исторический подробный статус до DOC-004 сохранён в `history/STATUS-before-DOC-004.md`.

## Последний frozen canonical checkpoint

`P1-CHAT-SCROLL-001` принят как текущий frozen canonical checkpoint от exact source:

- source SHA `1de74f79c47885b4e6ff1b1abfd0e695ae8858fd`, PR #255;
- base `a38796af702c698cda68ef2135c047823ba3b52b`;
- Foundation CI `37112301297` — SUCCESS;
- Dependency Security `37112301322` — SUCCESS;
- Review Source `37112301315` — SUCCESS.

Ему предшествовали принятые canonical checkpoints `PRE-P1-STABILIZATION-001` и
`PRE-P1-STRUCTURAL-MAINTENANCE-001`.

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
