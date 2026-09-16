# FRONTEND-001 — owner visual acceptance checklist

Status: **staging review aid / no acceptance recorded here**.

Frozen source under review: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.
PR: `#36 FRONTEND-001: Chat-first semantic product frontend`.

This checklist exists to make the owner decision explicit and reproducible. It does not mark the package accepted by itself.

## Evidence to review

Exact-head GitHub Actions evidence is from Foundation CI run `34948932137`, artifact `browser-evidence`, bound to the frozen source above.

Representative Chat-home evidence covers:
- 360×800;
- 390×844;
- 768×1024;
- 1024×768;
- 1440×900;
- 1920×1080;
- 2560×1440;
- 3840×2160;
- HiDPI projects.

The staging visual review is recorded in `FRONTEND_001_VISUAL_AUDIT.md`.

## Owner review questions

### 1. Product hierarchy

Confirm whether the current shell reads correctly as:

- Chat = main creative entry;
- Image / Video / Audio / 3D = first-class creative workspaces in the global strip;
- Feed and Gallery are separate utility/content surfaces;
- Account/Help/Balance remain secondary navigation.

Do not judge unsupported Video/Audio/3D preview cards as final studios; they are explicitly placeholders in FRONTEND-001.

### 2. Desktop geometry

At 1440×900 and 1920×1080 verify:

- left sidebar density is acceptable;
- top product navigation is not visually overloaded;
- heading/composer feel centered and deliberate;
- 768 px bounded Chat measure is comfortable;
- empty-state whitespace feels intentional, not unfinished.

### 3. QHD / UHD scale

At 2560×1440 and 3840×2160 verify:

- Chat remains readable without stretching content across the screen;
- heading/composer are not perceived as too small at 100% browser zoom;
- sidebar/main-canvas proportion remains acceptable.

If scale needs adjustment, prefer bounded typography/control tokens; do not widen the reading measure across the entire viewport.

### 4. Phone / tablet

At 360×800, 390×844 and 768×1024 verify:

- composer remains above the bottom Chat/Feed/Gallery navigation;
- primary actions are reachable without hover;
- creative workspace strip is understandable even when not all five labels fit simultaneously;
- keyboard/safe-area expectations are plausible for real-device follow-up.

### 5. Known mismatch intentionally deferred

Current exact-head Chat still visibly contains `Инструменты` in the composer. UX v4 establishes that this manual workspace picker is not the final product model.

Owner acceptance of FRONTEND-001 may therefore be either:

- acceptance of the current shell baseline with `Инструменты` explicitly scheduled for the bounded next Chat reconciliation package; or
- rejection pending removal of that control.

The choice must be explicit. Do not silently treat the known mismatch as resolved.

### 6. States not visually proven by the current artifact

Current retained Chat screenshots are primarily empty-state/light-theme evidence. They do not visually prove:

- active conversation after first user turn;
- dark-theme Chat composition;
- long/multiline composer at maximum practical height;
- real mobile keyboard/WebView behavior.

These gaps do not invalidate the green CI, but the owner may require them before visual acceptance.

## Decision format

Record one of the following outcomes in the PR conversation, with the exact frozen source SHA:

### Accept baseline

`OWNER_VISUAL_ACCEPTANCE ACCEPT source=5c0e79b6fc3a7120207d0889b176fbfed3dab973 follow_up=remove-manual-chat-tool-picker`

Meaning: current FRONTEND-001 shell is accepted as the baseline; the known manual `Инструменты` mismatch is explicitly delegated to the bounded follow-up package.

### Accept only after targeted evidence

`OWNER_VISUAL_ACCEPTANCE PENDING source=5c0e79b6fc3a7120207d0889b176fbfed3dab973 reason=<what must still be shown/fixed>`

### Reject baseline

`OWNER_VISUAL_ACCEPTANCE REJECT source=5c0e79b6fc3a7120207d0889b176fbfed3dab973 reason=<visual/product defect>`

This owner marker is a project convention for human clarity; it is separate from the machine-enforced independent-review marker in `tools/review_evidence.py`.

## Self-check

This checklist does not claim acceptance, does not alter source, and does not weaken the independent-review or CI gates.