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
