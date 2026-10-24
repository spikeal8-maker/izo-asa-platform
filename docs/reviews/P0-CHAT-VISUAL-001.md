# P0-D · Visible Chat + Admin UI redesign

This is a distinct **frontend-only** PR stacked on the test-only P0-B2/C
functional branch, which is stacked on unmerged PRs #280 and #279.
Base after integration: `0ab3cbaf596344a0678ee074e96ff3d4c2a2bf85`.
No changes to Chat/Graph/Accounts/API/SSO/paid workers/database/runtime network.

## What is visually changed

- Persistent desktop history workspace is now a dark navy sidebar with
  a distinguishable violet New Chat action, active-row accent, compact
  section labels, themed search and account footer.
- Messages use a clear role hierarchy: distinct user bubble,
  light assistant response card, branded reply marker,
  structured Markdown/quote/code styles and quieter actions.
- Composer becomes a tighter floating panel with clearer model selector,
  focus treatment, send/stop and accessible control targets.
- Main pane uses structured toolbar/branch status and subtle surfaces.
- Admin navigation, editable form fields and provider status are aligned
  to the same visual tokens without changing permission logic.
- Responsive mobile drawer, input state and focus remain real behavior.
- Dark theme receives its own contrast/accessibility overrides.
- Reduced-motion preference respected for added transitions.

## Confirmed test evidence

- Production TypeScript + Vite build passed on independent UX worktree.
- Playwright laptop (1440) / phone (390): 4 new checks PASS
  for history, drawer, model picker, controls, no horizontal overflow.
- Captures were made from the **same completed and persisted** fake
  conversation. Before and after source CSS were compared in a real
  Chromium session; the new CSS was injected as a replacement same-origin
  stylesheet response without weakening Content Security Policy.
  Main geometry and message content were held constant.
- Desktop BEFORE: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_D_Desktop_BEFORE.png`
- Desktop AFTER: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_D_Desktop_AFTER.png`
- Mobile BEFORE: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_D_Mobile_BEFORE.png`
- Mobile AFTER: `C:\Users\spike\Projects\izo-asa-p0-preview-qa\P0_D_Mobile_AFTER.png`
- Visual comparison proof: `P0_D_comparable_qa.json` in same local
  QA folder. Screenshots deliberately not tracked in Git (hygiene).
- A new exact-source UX preview on D2-R2 and full GitHub CI remain
  deployment gates; no claim of independent APPROVED from authored QA.

## Non-goals

- No removal/breakage of Rename, Search, Regenerate, Edit, Branches,
  Markdown/SSE, BYOK or platform fake model.
- No paid/production inference, owner access promotion, changed limits,
  CSS-in-JS CSP bypass, tracking large binary images or discarded user data.
- No main merge or owner waiver; independent read-only review required.

## Exact-source CI correction (successor commit)

The initial P0-D source (`fe13d2d739cacf5e9669d0fbf9f034d6dc0ee717`) failed
full Foundation CI on existing layout/semantics constraints:
body-theme prose color, mobile scroll retention after rename, composer
maximum width, 280px laptop sidebar and 8K scaling. The new CSS had
overridden inherited sizing and introduced extra chat-turn vertical spacing.

The correction **removes those new layout overrides** without modifying
test expectations, production behavior, design-system limits or the
underlying Chat/Graph/Accounts modules. Existing media-aware sizes,
scroll geometry, font scale and focus behavior are again owned by
the original Chat CSS. Navy sidebar, high-contrast active rows,
assistant response surfaces, input focus, Admin styling and dark theme
still differ substantially from the original UI.

Before committing, the 36-title targeted Playwright matrix on D2-R2:
**18 PASS / 0 FAIL / 18 SKIP** (skips are intentionally inapplicable
project/test combinations). Includes old Rename/scroll, Markdown theme,
composer width, focus after Graph selection, laptop shell and 8K shell.
Full GitHub CI must be repeated on the new exact SHA, not treated as
already passing based on targeted results.


## Mobile drawer during initial authentication — 24 October 2026

- Exact prior #282 source `14f3415493c6f96c458e3e3840787db95117e479` failed real Compose acceptance at `chat-live.mjs:221`: the renamed row was absent from the accessibility tree after reload and the mobile drawer was closed.
- Root cause: `App.tsx` rendered `ChatPage` using the temporary `guest` React key before `/api/v1/auth/me` resolved; the authenticated key then remounted Chat, discarding a just-opened mobile drawer. No PostgreSQL title loss was demonstrated by that failure.
- New isolated deterministic Playwright test deliberately holds the initial auth request. **Before** gating, the opener was wrongly clickable and the test failed on both initial run and retry. **After** gating, interactive Chat mounts only once initial session resolution completes; the same test passes.
- D2-R2 exact-worktree validation: production TypeScript/Vite build PASS; P0 visual **12/12 PASS** (phone/laptop); Sidebar/Rename/Search/Responsive **42 PASS, 18 intentional project skips, 0 failed, 0 retry**; repository hygiene PASS; no paid provider calls.
- New exact-source GitHub CI and independent review remain mandatory. Do not count targeted browser results as completed real Compose restart acceptance.
