# FRONTEND-001 · SELF_REVIEW

Verdict: **SELF_REVIEW PASS · FREEZE REQUIRES EXACT-HEAD CI · OWNER VISUAL ACCEPTANCE PENDING**

## Scope

Base: frozen `MAINT-AGENT-002`. Package class: `cross_domain`, risk `high`, with independent review required.
Backend business logic, migrations, provider spend, Credits/Jobs/Media semantics and merge/deploy remain non-goals.
Final scope is intentionally capped at **32 changed paths**; the cap was not raised to absorb the edge-policy correction.
The only edge-security change is the narrow Gallery requirement `img-src ... blob:` in `infra/Caddyfile`; no other CSP directive is relaxed.

## User result reviewed

- base visual system is monochrome light/dark: white/black/gray; color is reserved for semantic states;
- shell orchestration stays in `App.tsx`, while `TopBar.tsx` owns the compact top/mobile navigation and primary sidebar presentation;
- Studio is no longer a near-limit page component: orchestration/presentation owners are explicit;
- Account, Admin and Access near-limit pages were split without moving security-sensitive handlers away from their block owners;
- Feed/Gallery/Admin/Account/Studio use one flatter visual language instead of unrelated legacy card palettes;
- mobile topbar and bottom navigation remain product navigation rather than page-specific UI;
- the Studio primary action stays above the fixed mobile bottom navigation while the composer is in view, so the main action is not obscured on phone viewports;
- Gallery work detail no longer presents itself as a private server-storage/test-file screen; download and ownership behavior are unchanged;
- unsupported Chat/Video/Audio/3D runtimes are not faked.

## Regression review

The first state/split CI exposed three stale structural assumptions: generated CURRENT, package-specific state assertions and an IMAGE boundary tied to the old Studio owner. They were fixed by restoring generated state, making the state regression generic and moving the boundary to Composer.

The Account/Admin/Access split then exposed one real UI regression: ACCESS scope was no longer visible. The test was not weakened; visible `scope: global` was restored.

Browser evidence exposed additional defects that pass/fail alone did not catch: technical Gallery-detail language, private-preview CSP blocking validated blob URLs, and the phone Studio primary action landing under the fixed bottom navigation. The Gallery language was simplified, CSP was corrected only for `img-src blob:`, and the mobile action is now sticky inside its composer above the bottom navigation.

## Maintainability delta

- old `Studio.tsx` (~10.7 KB before FRONTEND-001) is now a thin page composition; the main `Composer.tsx` remains below the 80% production headroom threshold after its own split;
- `AccountPage.tsx`, `AdminPage.tsx` and `AccessPage.tsx` were reduced from near-limit pages to orchestration owners, with presentation in small sibling modules;
- navigation presentation was consolidated into `TopBar.tsx` rather than increasing the package file budget for the CSP correction;
- new handwritten files were reviewed against the 12 KB / 300-line production hard limit and 80% headroom rule;
- BLOCK_MAP ownership follows the real quote/submit/theme handlers after the split;
- Account/Admin local README maps point small UI changes to presentation owners instead of broad page files;
- no context/file/scope limit was increased to obtain CI green;
- no new dependency, migration, generated API contract or backend runtime owner was introduced.

## Security / ownership

Auth/session mutations remain server-authorized. ACCESS load/mutate handlers still own stable operation IDs, fresh-password handling and permission allowlists. Admin compensation still uses the existing GrantForm and backend permissions. Gallery preview/download still obtains fresh bounded authenticated bytes and validates metadata/hash through the existing media transport. `blob:` is permitted only as an image source so those already-validated private bytes can be decoded by the browser; script/connect/object policy is unchanged.

## Acceptance boundary

Technical CI is necessary but **not sufficient** to close FRONTEND-001. Freeze requires successful required workflows bound to the final source head, followed by owner visual review of the final browser evidence / Docker build on mobile and desktop-class screens. Until that acceptance, later Feed/Chat/Video/Catalog UI packages must not treat the shell as owner-approved.
