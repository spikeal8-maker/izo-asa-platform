# UX v4 Coverage Report

Snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`

- User pages covered: **45/45**
- Admin pages covered: **30/30**
- Total page registry: **75/75**
- Pages with explicit conflict/route-decision markers: **5**
- Complex workspaces with dedicated modules: **Chat, Image, Video, Audio, 3D**
- Cross-workspace journeys: **10** (from v3)
- Shared component contracts: **added in v4**
- Lineage/versioning contract: **added in v4**
- Current API/owner-file snapshot: **added in v4**
- Machine-readable page registry + validator: **added in v4**

## Explicit unresolved rows

- `U-01` Главная — `TARGET-CONFLICT` — Current FRONTEND-001 already uses / as Chat; historical PRODUCT described marketing home.
- `U-09` Рабочее пространство — `RETIRED/ALIAS-CANDIDATE` — Historical PRODUCT route. V4 does not create a second hub; Chat is home.
- `U-11` Image Editor — `TARGET-ROUTE-DECISION` — Capability is required; whether /paint remains standalone vs integrated editor is unresolved.
- `U-15` Диалоги — `ROUTE-DECISION` — Historical thread-list route conflicts with / Chat-first home. Prefer alias/history surface, not second Chat product.
- `U-16` Чат thread — `TARGET-ROUTE-DECISION` — Thread deep-link useful; needs router decision with / home.

## Important repository lifecycle note

This package is an external implementation artifact. It is intentionally **not pushed into PR #36**: FRONTEND-001 is a frozen, high-risk package and repository documentation rules prohibit creating a second stable master/roadmap hierarchy. Reconciliation should be performed in the next permitted package by updating the existing canonical owners rather than dropping this folder wholesale into `docs/`.