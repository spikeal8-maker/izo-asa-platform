# FRONTEND-001 · SELF_REVIEW

Verdict: **SELF_REVIEW PASS · EXACT-HEAD CI PENDING · OWNER VISUAL ACCEPTANCE PENDING**

## Scope

Base: frozen `MAINT-AGENT-002`. Package class: `cross_domain`, risk `high`, independent review required.
Backend business logic, migrations, provider spend, Credits/Jobs/Media semantics and merge/deploy remain non-goals.

The owner revised the frontend contract while FRONTEND-001 was still active: Chat replaces Feed as the canonical `/`
surface and Semantic Color System v1.1 replaces the previous monochrome draft. Scope therefore moved from the earlier
32-path snapshot to a hard ceiling of **40**, with the actual package remaining at that cross-domain ceiling after the
navigation split and account regression update. This was an explicit product-requirement change, not a limit increase used
to make CI green.

The only edge-security change remains the narrow Gallery requirement `img-src ... blob:` in `infra/Caddyfile`;
no other CSP directive is relaxed.

## User result reviewed

- `/` and `/studio/chat` resolve to the new Chat home; `/feed` remains a separate Explore surface;
- `ChatPage.tsx` owns the primary chat/composer surface instead of inflating `App.tsx`;
- empty desktop Chat follows the supplied reference: one heading and a centered 768px composer, without invented quick-action cards;
- phone Chat keeps the composer at the bottom and respects the mobile safe-area/navigation space;
- global creative navigation is Chat / Image / Video / Audio / 3D;
- mobile keeps the same creative modes in the upper strip and a short Chat / Feed / Gallery bottom navigation;
- shell geometry follows the supplied chat reference: 260px desktop sidebar, 56px desktop header, bounded 768px conversation/composer and 94px two-row phone header;
- Semantic Color System v1.1 is now the runtime source through `theme.css`;
- existing components consume compatibility aliases that point back to the semantic tokens, so future approved palette changes are centralized;
- violet is the only brand color; creative modes do not receive separate decorative colors;
- hover/focus/selected states derive from tokens through `color-mix` rather than new component HEX values;
- Studio remains split into page composition + Composer/Result/Quote owners;
- Account, Admin and Access stay split without moving security-sensitive handlers;
- Gallery ownership/download semantics remain unchanged;
- text Chat does not fake a successful assistant response while the server runtime is absent;
- Video/Audio/3D runtimes remain presentation-only and are not reported as working generation backends.

## Regression review

Earlier FRONTEND-001 checks exposed stale generated state, package-specific assertions, an IMAGE boundary tied to the
old Studio owner, ACCESS scope disappearing after component split, private-preview CSP rejecting validated blob URLs,
and a phone Studio action overlapping bottom navigation. Those fixes remain in the current lineage.

The first chat-first Foundation run reached **818 passed / 2 failed** in Python/architecture. Both failures were structural,
not product-runtime failures: `layout.css` had crossed the 80% headroom threshold, and the owner-shell regression still
asserted the superseded feed-first wording. The size gate was not weakened. Product-header/mobile navigation CSS was split
into `product-nav.css`, bringing layout responsibility back below headroom. The documentation regression now asserts the
new chat-first owner contract and Semantic Color System v1.1 instead of preserving obsolete requirements.

The following browser run passed unit/architecture and then exposed deterministic frontend-test collisions across the viewport
matrix: browsers normalize CSS custom-property hex case; the old login regression still expected the former Feed heading on
`/`; and the new aria labels `Режим модели` / `Режимы ИЗО АСА` collided with the existing Studio field labelled `Режим`.
The palette was not changed to satisfy the test. Assertions now expect browser-normalized values, login explicitly verifies
Chat home, and navigation/model accessible names were disambiguated from the Studio form control.

Browser screenshots from that same run also showed two presentation issues not expressed by the failing assertions: the
empty desktop composer was docked too low versus the supplied chat reference, and the 1440px header became visually dense
because media queries considered the full viewport but not the 260px sidebar. The empty-state composer is now centered on
desktop, while phone keeps bottom docking; utility labels collapse at a wider breakpoint and creative labels collapse before
the remaining desktop header becomes crowded.

## Maintainability delta

- old `Studio.tsx` remains thin and `Composer.tsx` stays below production hard limits;
- `ChatPage.tsx` and `chat.css` are separate owners under `web.shell`, not additions to an existing near-limit page;
- `TopBar.tsx` owns navigation behavior while `product-nav.css` owns its desktop/mobile presentation; `layout.css` no longer accumulates both responsibilities;
- `AccountPage.tsx`, `AdminPage.tsx` and `AccessPage.tsx` remain orchestration owners with small presentation siblings;
- `theme.css` owns semantic tokens once; feature CSS references variables rather than copying palette HEX values;
- Feed returned to its frozen stylesheet to keep the package at 40 paths; its UI chrome still inherits v1.1 through shared aliases, while its illustrative artwork remains exempt from the UI palette by the color-system contract;
- `apps/web/AGENTS.md` points Chat and product-navigation changes to their small owners;
- scope remains `cross_domain <= 40`; tests/limits were not weakened;
- no dependency, migration, generated API contract or backend runtime owner was introduced.

## Security / ownership

Auth/session mutations remain server-authorized. Chat local presentation does not create a wallet, provider configuration,
server Job, fake assistant output or private Media ownership. Working image generation still crosses the existing
Entitlements → Credits → Jobs → Media contracts. ACCESS and Admin permission handling is unchanged. Gallery preview/download
continues to fetch bounded authenticated bytes through the existing Media transport.

## Acceptance boundary

This revision requires a new exact-head Foundation CI, Dependency Security and Review Source result; earlier green heads do
not transfer automatically. Technical CI is still not sufficient to close FRONTEND-001: the owner must visually review the
final Chat shell and inherited Feed/Gallery/Account/Admin surfaces on phone and desktop-class viewports before the package is
accepted as the base for later CHAT/FEED/VIDEO expansion.
