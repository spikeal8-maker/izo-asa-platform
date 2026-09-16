# IZO ASA UX v4 — traceability matrix

Status: **staging / verification aid**. This maps accepted direction and current facts to canonical doc owners, current code owners, tests and package boundaries. It is not a second roadmap.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

| Contract / requirement | Current evidence | Canonical doc owner | Current code owner | Nearest verification | Status / next boundary |
|---|---|---|---|---|---|
| `/` is Chat-first home | `App.tsx`, PR #36 | PRODUCT + UX shell | `shell/App.tsx`, `ChatPage.tsx` | `e2e/shell.spec.ts` | CURRENT; old PRODUCT home meaning needs reconciliation |
| Five creative workspaces | `navigation.ts`, TopBar shell | PRODUCT / UX | `shell/navigation.ts`, `TopBar.tsx` | shell E2E | CURRENT + owner direction |
| Chat is intent-driven, not permanent tool dashboard | owner UX v4 decision direction | PRODUCT / UX shell | `ChatPage.tsx` | new fail-first shell cases | TARGET; current `Инструменты` picker conflicts |
| `+` is attachment/context entry | UX v4 contract | UX | `ChatPage.tsx` | future Chat/Media tests | TARGET; must remain honest until server contract exists |
| No fake Chat success | current `ChatPage.tsx` unavailable notice | PRODUCT / UX | `ChatPage.tsx` | shell E2E | CURRENT invariant |
| Image generation works through server policy/quote/job/media | `Composer.tsx` | PRODUCT / ARCH / runtime owners | Studio + shared submission | studio/provider E2E + backend suites | WORKING; must not regress in frontend packages |
| Stable operation id protects unknown submit outcome | `Composer.submit`, shared submission | ARCH / runtime | `Composer.tsx`, `shared/submission.ts` | studio/provider tests | WORKING safety invariant |
| Jobs are operational truth, separate from Gallery | `ResultPanel.tsx`, PRODUCT target | PRODUCT / ARCH | `ResultPanel.tsx` | studio/provider tests | WORKING |
| Gallery is private Assets | current Media/Gallery path | PRODUCT / ARCH | `features/gallery/*` | gallery E2E + media boundaries | PARTIAL UI / WORKING ownership |
| Feed is separate public Publication surface | PRODUCT target; current fake editorial examples | PRODUCT / ARCH | `FeedPage.tsx` | shell now; FEED tests later | PLACEHOLDER until FEED-001 |
| Video real Studio | only generic `SectionPage` now | PRODUCT / UX / runtime | future `features/video/*` | VIDEO package tests | TARGET-ONLY runtime |
| Audio real Studio | only generic `SectionPage` now | PRODUCT / UX / runtime | future `features/audio/*` | AUDIO package tests | TARGET-ONLY runtime |
| 3D real Studio | only generic `SectionPage` now | PRODUCT / UX / runtime | future `features/3d/*` | THREE-D package tests | TARGET-ONLY runtime |
| Phone is transformed layout, not shrunken desktop | UX.md and active shell | UX | shell/feature CSS | viewport matrix | CURRENT contract; per-feature details later |
| Semantic color v1.1 | `theme.css`, PR #36 | UX | `shell/theme.css` | shell E2E token assertions | CURRENT |
| Admin A-01…A-30 are target registry, not all implemented | ADMIN + current `AdminPage` behavior | ADMIN | current admin feature subset | admin/access E2E | TARGET registry / partial implementation |
| Durable ChatThread route model | architecture target, no current runtime | PRODUCT / ARCH | future Chat domain + router | CHAT-001 tests | O-02 pending |
| Image editor route | old `/paint` target only | PRODUCT / UX | future IMAGE-002 | editor/ownership tests | O-03 pending |
| VideoProject persistence | none current | PRODUCT / ARCH/ADR if introduced | future video domain | project persistence tests | O-04 pending; default no project first release |
| AudioProject persistence | none current | PRODUCT / ARCH/ADR if introduced | future audio domain | project persistence tests | O-05 pending; default no DAW first release |
| 3D editing depth | generator/viewer target only | PRODUCT / UX | future 3D domain | modality tests | O-06 pending |
| Marketing landing need | old U-01 conflicts with Chat-first `/` | PRODUCT / UX | future only if accepted | route/E2E | O-07 pending |
| Lineage/version graph beyond source links | source links exist conceptually/current Asset relation; no version graph contract | ARCH/ADR | future Media/editor domains | lineage persistence tests | O-08 pending |
| Exact-head package freeze | DEVELOPMENT/project_state | PLAN/DEVELOPMENT process | `tools/project_state*` | `tests/test_project_state.py` | CURRENT process invariant |
| High-risk independent review | MAINTAINABILITY/review tool | process docs | `tools/review_evidence.py` | project-state tests | CURRENT gate |
| decides-next continuation from null | current code deadlock | process tooling | `project_state.py`, model | project-state tests | BUG #188; repair required |

## Traceability rules

1. A `CURRENT` implementation fact is not automatically a permanent product decision.
2. A `TARGET` UX line does not authorize fake backend behavior.
3. A pending O-01…O-08 decision must be resolved in canonical docs before corresponding route/data-model implementation.
4. Shared shell packages may only touch domain owners when a regression proves necessity; they do not absorb domain business logic.
5. Any safety-critical Image/Jobs/Auth/Media semantic change requires the owning backend/domain tests, not only browser mocks.

## Coverage self-check

The matrix explicitly traces the five workspaces, Gallery, Feed, Jobs, Account/Admin boundaries, responsive/color contracts, all eight open owner decisions and lifecycle safety. Detailed page-level coverage remains in the archived 45-user/30-admin v4 package rather than being duplicated here.