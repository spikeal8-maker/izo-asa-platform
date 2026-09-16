# 00A — Decision Register

This is the conflict-resolution layer for UX v4. It does **not** override repository-owned stable docs by itself. It tells an implementation agent which statements are confirmed, which are current implementation facts, and which require an explicit owner/package decision.

Snapshot: `spikeal8-maker/izo-asa-platform` / `ux/frontend-reset` / `FRONTEND-001` at `5c0e79b6fc3a7120207d0889b176fbfed3dab973` (checked 2026-09-16). PR #36 is still draft and unmerged.

## Status vocabulary

- **OWNER-CONFIRMED** — directly established by owner direction in the active design work.
- **CURRENT-IMPLEMENTED** — observed in the current branch; not automatically a permanent product decision.
- **REPO-TARGET** — stated in PRODUCT/UX/ADMIN target docs.
- **V4-PROPOSED** — design proposal awaiting product/runtime acceptance.
- **CONFLICT** — current docs/implementation/owner direction disagree; implementation must not silently choose.

## Register

| Decision | Status | V4 contract | Implementation consequence |
|---|---|---|---|
| D-001 Product has five top-level creative workspaces | OWNER-CONFIRMED + CURRENT-IMPLEMENTED | Chat / Image / Video / Audio / 3D | Keep in global creative navigation. |
| D-002 Chat is intent-driven, studios are tool-driven | OWNER-CONFIRMED | Chat hides internal routing; studios expose direct domain controls | Do not turn Chat into a permanent tool dashboard. |
| D-003 Visible Chat tool picker | CONFLICT | Remove persistent `Инструменты` picker from final Chat; `+` is for attachments/context | Current `ChatPage.tsx` is transitional. |
| D-004 `/` as Chat home | OWNER-CONFIRMED + CURRENT-IMPLEMENTED, conflicts with older PRODUCT U-01 | `/` is target Chat home | Old marketing-home meaning needs PRODUCT reconciliation. |
| D-005 `/app` hub | CONFLICT | No second creative hub in V4 | Treat as legacy/redirect candidate only after route decision. |
| D-006 `/chat` and `/chat/{threadId}` | REPO-TARGET + V4-PROPOSED | Preserve deep-linkable threads, but do not duplicate Chat product | Decide alias/history semantics before router change. |
| D-007 `/studio/*` routes | CURRENT-IMPLEMENTED compatibility | New links use concise routes; aliases may remain for backward compatibility | Router owns redirects/aliases; feature code does not emit `/studio/*`. |
| D-008 Image editor `/paint` vs integrated editor mode | CONFLICT | Capability is required; route ownership unresolved | Do not delete `/paint` contract or invent final route without package decision. |
| D-009 Video timeline/project | V4-PROPOSED | Only after a real VideoProject domain object exists | Generation workspace must work without fake timeline persistence. |
| D-010 Audio multitrack project | V4-PROPOSED | Core audio first; AudioProject only if product/runtime accepts it | Do not implement DAW semantics as CSS-only state. |
| D-011 3D full modeling | V4-PROPOSED / OUT OF EARLY SCOPE | Level A generator/viewer first | Scene/material editing is later; full CAD/modeling is not implied. |
| D-012 Chat desktop history sidebar | V4-PROPOSED | Allowed if it stays subordinate to conversation | Do not let it turn home into a dense dashboard. |
| D-013 Gallery vs Jobs | OWNER-CONFIRMED + REPO-TARGET | Gallery=private assets; Jobs=operational execution history | Never merge them into one history list. |
| D-014 Feed privacy boundary | REPO-TARGET | Publication is a separate public object referencing an Asset | Publishing never makes source metadata public by accident. |
| D-015 Editable Project/Document entities | V4-PROPOSED | Only create when backend persistence/version semantics are defined | Session history is not a substitute for a Project entity. |
| D-016 Phone adaptation | REPO-TARGET | Same essential actions, transformed layout, no shrunken desktop | Every complex page needs explicit phone state/order. |
| D-017 Semantic color v1.1 | CURRENT-IMPLEMENTED + OWNER-DIRECTION | Neutral UI + one violet brand accent | No per-workspace decorative palette. |
| D-018 Owner visual acceptance | CURRENT PROCESS GATE | Automated checks do not equal visual acceptance | FRONTEND-001 remains frozen/draft until owner and independent review gates are satisfied. |

## Conflict rule

When a row is `CONFLICT`, a coding agent may prepare implementation notes/tests, but it must not silently convert the V4 proposal into a canonical repository rule. The conflict must be resolved in the appropriate package and reconciled into repository-owned docs (`PRODUCT.md`, `UX.md`, `ADMIN.md`, ADR where architecture changes).
