# Chat UI ownership

`../ChatPage.tsx` owns layout/sidebar state; `../chat.css` owns grid, empty state and drawer geometry. `ChatSidebar.tsx`/CSS own history/search/rail/profile; `ChatComposer.tsx`/CSS own input geometry. `TopBar` keeps the global header outside Chat.

Expanded/compact desktop state is a UI preference only. Hidden mobile history leaves the keyboard order; dismissal or desktop-to-mobile resize restores focus. Open history is a modal with inert background and contained focus. Dismissal clears search/profile state; New/Open Chat close the drawer. Empty heading and composer form one block; narrow controls may wrap.

The picker uses server Chat policy, OpenRouter text catalog and informational RUB prices. Unknown RUB stays unknown even when USD metadata exists. UI cannot grant access, publish models, set prices, choose provider keys or debit Credits. Policy/catalog freshness is checked before submit; accepted-request replay remains authoritative. Keys and raw provider endpoints are never browser preferences.

`AttachmentControl` owns PNG/JPEG/WebP selection, paste/drop, ordered previews and the five-image limit. `chatAttachments` validates bytes/dimensions and uses shared Media uploads with stable operation IDs. Uncertain uploads are checked before repeating. An account Web Locks lease prevents cross-tab reuse; without Web Locks image upload is explicitly unsupported. Composer checks vision capability/price before submission; runtime checks again after upload. Replaying a Chat request first reads its ID; if absent, freshness is rechecked before POST.

Only per-account operation UUID, file hash/type/size/dimensions and started status persist for upload reconciliation. Image bytes/names remain in memory; the same file must be reselected after reload. Unavailable files cannot resume from storage. Add/remove freezes during preflight/send. Saved images use the shared private-image hook; unsupported tools stay disabled.

Chat admission IDs live only in memory. Closing/reloading after an uncertain POST loses its identity; New/Open Chat retain the draft and exact ID within that tab. Media recovery does not prove paid Chat admission. Cross-tab recovery needs a separate privacy-aware design.

Nearest tests: `chat-attachments.spec.ts`, `chat-sidebar.spec.ts`, `chat-responsive.spec.ts`, `catalog.spec.ts`, `shell.spec.ts`.

## Canonical routing

This shell owns Chat. Canonical contracts: `PRODUCT.md` (behavior), `UX.md` (interaction), `ARCHITECTURE.md` (branches/context), `MAINTAINABILITY.md` and `DEVELOPMENT.md` (process), all in `docs/`. Proposals are provenance only.

Long-thread history loads older server pages through `useThreadSelection`; the
exclusive sequence cursor and loaded messages live only in current account/thread
UI state. `App.tsx` keys the Chat page by account identity so changing account
clears its private history before paint. `useChatScroll` compensates for
prepended content before paint and holds the visible message anchor through
later private-image layout changes. User scroll input releases that anchor.
Late pages from a prior selection are ignored.
`chat-history-paging.spec.ts` covers desktop/phone, reload and stale responses.

`useThreadHistory` loads sidebar thread history beyond the first 50 through a server cursor.
It keeps already loaded rows unique by thread ID, resets to the first page on
reload/account change, and offers an explicit older-chats control in desktop
sidebar and phone drawer. `chat-thread-paging.spec.ts` covers both viewports.

`ThreadRenameForm`/`useThreadRenameEditor` own inline draft, Unicode validation, save/cancel/errors and focus return after editor removal and PATCH unlock; deliberate focus changes cancel that return. The sibling action stays visible on touch. Escape cancels editing before the drawer. `useThreadHistory` changes only the confirmed title while retaining pages/cursor/selection. Its request revision fences reads begun before/during rename; later fresh reads preserve the loaded tail. Account teardown clears rename state. Rename and rename-races specs cover recovery, viewports, frame ordering and focus; `acceptance/chat-live.mjs` proves PostgreSQL restart and concurrent first-message naming.

## Response variants

`ThreadDetail.graph_version=1` selects the additive Graph API; its failures are explicit. Legacy physical message endpoints/cursors keep their contract. `useConversationGraph` projects immutable ordered turns into the existing renderer, merges bounded pages without dropping loaded history, fences account/thread/branch/revision reads and preserves observed terminal lifecycle. Assistant DOM keys use turn identity; persisted selection and display sequence choose content/order. `useChatScroll` preserves the reading anchor before confirmed replacement.

`useAssistantAttempts` owns regeneration, completed-only previous/next selection and reconciliation. Fresh commands use server revision CAS. Regeneration retains its UUID after uncertain admission and first checks that request; no new paid operation is silently substituted. The old completed response remains through pending/failure; only server-confirmed selection replaces it. UNKNOWN blocks new execution. The SSE runtime resumes pending attempts, respects confirmed terminal state and refreshes Graph even for turns outside the newest page. Controls remain keyboard/touch accessible and preserve deliberate focus changes.

`conversation-graph.spec.ts` and `conversation-graph-races.spec.ts` cover variants, replay, paging, focus, mobile and races. `acceptance/chat-graph-live.mjs` extends the isolated browser/PostgreSQL before/after restart proof using fake providers and ordinary authenticated endpoints.
