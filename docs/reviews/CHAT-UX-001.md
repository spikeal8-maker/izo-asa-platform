# CHAT-UX-001 · implementation contract

## Before → after

Before: the desktop Chat sidebar is either fully open or absent. The closed mobile drawer is translated offscreen but its controls remain in keyboard order. The empty-state heading and composer share a block, yet viewport-dependent bottom padding shifts that block above its working-area center. The 29-file `ux/chatgpt-experience-001` worktree is based on a divergent OpenRouter lineage and has no compact rail; it is a reference, not an implementation source.

After: desktop Chat switches between an expanded history panel and a compact, useful icon rail; the choice survives reload as a local UI preference. New chat, history expansion and search remain reachable in the compact state. Mobile Chat starts with a closed, non-focusable drawer; opening it overlays the main area, while Escape, backdrop and selecting a chat close it with predictable focus. The empty heading, note and composer stay centered as one block within Chat main at 320px, desktop and large screens. Existing header, server model/price preflight and message runtime remain intact.

## Fixed scope

- Package/base: `CHAT-UX-001` from `codex/admin-donor-catalog-001@ed1f79a6c53bdc3cab5d827d308ee661a61ebd20`.
- Normal machine scope: at most 18 declared files. Owner: web Chat surface and its responsive E2E. Local UI preference may use browser storage; identity, permissions, price and provider configuration remain server-owned.
- Do not copy the dirty E: checkout wholesale. Its narrower widths and composer spacing are visual references only; its 8K assertions weaken the canonical product contract, and its OpenRouter/vision changes have different runtime ownership.
- Non-goals: top bar, backend/HTTP contracts, Chat image tool, real provider calls, Credits/Jobs/Media, merge or release.

## Risk and nearest acceptance

Risk: medium, mainly focus access, viewport transitions and visual geometry. First failing case in `chat-sidebar.spec.ts`: at 1440px collapsing the panel must leave a usable 56–72px rail and reflow the main; at 320px the initially closed history must have no focusable descendants, open over the main, close on Escape/backdrop/selection and restore focus. Empty Chat heading and composer must form a centered block without overflow at 320px/1440px; fluid type and controls must continue growing at 2K/4K/8K. Run a failing browser case before implementation, then build, affected viewport specs, self-review and full required CI.

Red acceptance before source edits: `npx playwright test e2e/chat-sidebar.spec.ts --project=laptop --project=phone-small --max-failures=3` exited 1. The old layout has no desktop rail (collapsed width 0), the closed 320px drawer has no `aria-hidden` or `inert`, and the heading/composer content center is displaced by 36px (12px tolerance).

## Self-review

Verdict: **PASS** for the finite Chat layout package. The desktop rail remains usable after collapse and the main reflows; mobile history is a modal drawer whose closed state is inert. Escape, backdrop, selection and new chat restore focus, and a desktop-to-mobile resize moves focus out of the now-hidden history. Search and profile state reset on mobile dismissal. The heading and composer remain one centered block; the 320px composer uses two rows to avoid control overlap. The shared header source, Chat runtime, policy freshness, provider/price ownership and Credits paths are unchanged.

The first frontend pass found two P2 focus regressions during independent read-only review and a P3 stale-search regression during implementer review. Each was reproduced with a browser acceptance case before its correction. Independent read-only QA then reported PASS on the corrected diff; this is local QA, not a GitHub `APPROVED` review. A final visual inspection of the local Docker preview found that a wrapped guest note remained left-aligned at 320px (18.34px text-center offset); a red browser case preceded its centered alignment fix.

Verification on Windows: `npm run build` PASS; `npx playwright test e2e/chat-sidebar.spec.ts e2e/chat-responsive.spec.ts e2e/shell.spec.ts e2e/catalog.spec.ts --project=laptop --project=phone-small` 50 passed, 10 skipped; `npx playwright test e2e/shell.spec.ts --project=eight-k` 1 passed; `tools/export_contracts.py --check` in the project venv, `python tools/project_state.py verify`, `python tools/check_docs.py`, `python tools/check_change.py --base ed1f79a6c53bdc3cab5d827d308ee661a61ebd20 --scope tools/scopes/chat-ux-001.json`, and `git diff --check` PASS. Full required GitHub CI remains the technical acceptance gate.

Maintainability delta: 16 changed paths in the normal 18-file scope; no source outside Chat layout/tests or allowed docs/state. Changed production files are below the 12 KiB/300-line hard limit (largest: `ChatComposer.css` 9,474 B, 289 lines; `ChatPage.tsx` 8,910 B, 213 lines). Changed E2E files are below 16 KiB/350 lines (`chat-responsive.spec.ts` 12,501 B; new `chat-sidebar.spec.ts` 12,286 B). The new Chat route starts at 4,379 B; local owner README remains short. No generated files, lockfiles or artifacts changed. The next Chat edit should avoid growing composer CSS without splitting its owner area.

Open package limits: physical-device keyboard/VisualViewport behavior needs the existing release check. Image input/output and provider execution are separate product packages with their own ownership and cost gates; this layout package does not claim them.
