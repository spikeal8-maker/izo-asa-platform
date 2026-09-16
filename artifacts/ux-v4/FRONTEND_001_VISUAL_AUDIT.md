# FRONTEND-001 visual evidence audit

Status: **staging visual review / not owner acceptance**. This is an independent second-pass inspection of the GitHub Actions browser evidence. It does not satisfy the repository's required independent-review evidence and does not replace the owner's visual decision.

Frozen source: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

Evidence source: Foundation CI run `34948932137`, artifact `browser-evidence` (`artifact id 10389115346`, digest `sha256:dfff4a0411a0ce540b6106e821cfbc9072c5b47117dbca8621ace5bbf436576c`). The artifact is bound to the same frozen head.

## Evidence actually present

The archive contains `chat-home.png` for:

- 360x800 phone-small;
- 390x844 phone;
- 768x1024 tablet;
- 1024x768 tablet-landscape;
- 1440x900 laptop;
- 1920x1080 desktop;
- 2560x1440 QHD;
- 3840x2160 UHD;
- HiDPI 150% and 200% projects.

It also contains screenshots for existing Admin/Access/Gallery/Image/Studio surfaces, including live server-backed evidence.

## What the empty Chat evidence confirms

### Pass

- Chat is visibly the primary surface: one heading and one composer dominate the page.
- Desktop keeps a stable left product sidebar and a compact top navigation.
- The conversation measure stays bounded instead of stretching text/composer across QHD/UHD.
- Phone layouts keep the composer above the short Chat/Feed/Gallery bottom navigation; no obvious overlap is visible in the supplied 360/390 evidence.
- Tablet portrait uses the phone-style product shell without turning into a squeezed desktop sidebar.
- Tablet landscape switches to the desktop-style sidebar without visible document-level horizontal overflow.
- The neutral light palette + violet selection state is consistent across the shown Chat surfaces.

## Confirmed visual/product mismatch

The composer visibly contains **`Инструменты`** on phone, tablet and desktop screenshots. This is not merely hidden code: it is part of the actual reviewed UI.

That control is the main known mismatch with the new UX v4 contract. It duplicates the global Chat/Image/Video/Audio/3D navigation and teaches the wrong mental model (manual workspace routing from inside Chat). The bounded next package correctly targets its removal.

## Review items that are not CI failures

### 1. Phone discoverability of all five creative modes

At 360/390 px the creative strip is horizontally constrained; the screenshot does not show all five labels simultaneously. The E2E asserts that five links exist, but existence is not the same as discoverability.

Current requirement allows horizontal reachability, so this is not a technical failure. During owner review, verify that Audio/3D are obvious/reachable without users assuming the strip ends at the last visible item. A subtle overflow/scroll affordance may be preferable if real-device review shows confusion.

### 2. QHD/UHD perceived scale

The 768 px Chat measure is correctly bounded, but on 2560/3840 CSS-pixel screenshots the central heading/composer occupy a small fraction of the canvas and the page contains very large empty areas.

This is partly intentional for a sparse ChatGPT-like home. Owner review should decide whether current typography/control scale is comfortable at true 100% QHD/UHD, rather than widening the reading measure. If adjustment is needed, prefer typography/control tokens or a bounded clamp; do not stretch chat text to the full screen or apply global CSS scaling.

### 3. Sidebar density on very large screens

The sidebar remains narrow and mostly empty on QHD/UHD, with Help/Tokens/Account anchored near the bottom. This is structurally consistent, but visual acceptance should confirm that the contrast between a very sparse sidebar and very sparse main canvas feels intentional rather than unfinished.

## Missing visual evidence for owner acceptance

The current `chat-home.png` matrix is **empty-state light-theme evidence**. It does not, by itself, visually prove several states mentioned in the PR/product contract:

1. **Active conversation state** after the first user turn, where composer should move to the bottom dock without covering messages.
2. **Dark theme appearance** of the full Chat surface. The test checks theme state/tokens, but the archived Chat screenshot matrix is not a dark-theme visual set.
3. **Manual tool popover open state** (currently obsolete anyway).
4. **Long/multiline composer** behavior near its max height on phone and desktop.
5. **Mobile keyboard viewport** behavior on a real device/WebView; screenshots without an OS keyboard cannot prove this.

These are not reasons to invalidate the green CI, but they are gaps if the owner wants a visual—not merely behavioral—acceptance of the final shell.

## Recommended visual acceptance evidence for the next shell pass

Keep the existing empty-state matrix, then add a much smaller targeted visual set rather than multiplying every state by every viewport:

- 390x844: empty Chat, one submitted user turn, multiline composer;
- 1440x900: empty Chat + active conversation;
- 1920x1080: dark Chat active conversation;
- 3840x2160: empty Chat scale check;
- one real-device/mobile-WebView check with keyboard open.

The full automated viewport matrix can remain behavioral; only representative visual states need retained screenshots.

## Inherited surfaces

The artifact contains server-backed screenshots for Studio, Gallery, Admin/Access and Credits. The bounded Chat reconciliation should not restyle those surfaces incidentally. Shared shell changes should be checked against them, but domain redesign belongs to their own packages.

## Verdict

**TECHNICAL VISUAL EVIDENCE IS CONSISTENT WITH THE CURRENT FRONTEND CONTRACT, BUT OWNER VISUAL ACCEPTANCE SHOULD REMAIN PENDING.**

The manual `Инструменты` control is a confirmed target mismatch, and the artifact does not visually cover active-conversation or dark-theme Chat states. The next bounded Chat package should fix the picker and add targeted visual evidence without expanding into backend/runtime or unrelated surface redesign.