# Chat UI ownership

`../ChatPage.tsx` owns the Chat layout and sidebar presentation state. `../chat.css` owns its grid, empty-state alignment and drawer geometry. `ChatSidebar.tsx` and `ChatSidebar.css` own history, search, compact rail and profile controls; `ChatComposer.tsx`/`ChatComposer.css` own input geometry. Keep the global header in `TopBar`, outside this feature.

Expanded/compact desktop state is a browser UI preference only. Hidden mobile history must leave the keyboard order and restore focus on dismissal or desktop-to-mobile resize. Open mobile history is a modal dialog with inert background and contained focus; dismissal clears transient search/profile state. New chat and selection close the drawer. The empty heading and composer form one layout block; narrow composer controls may use a second row.

The model picker uses the server Chat policy, OpenRouter text catalog and
informational RUB prices. An unknown RUB price is shown as unknown, including
when OpenRouter supplies separate USD metadata. UI state cannot grant
permissions, publish a model, change price, select a provider key or debit
Credits. Keep the policy/catalog freshness check before submit and preserve
accepted-request replay behavior. Provider credentials are configured through
the same server-owned Chat API; no key or raw provider endpoint is stored as a
browser preference. `AttachmentControl` owns PNG/JPEG/WebP selection,
paste/drop, ordered previews and the five-image limit. `chatAttachments`
validates bytes and dimensions, then uses shared Media uploads with stable
operation IDs; an uncertain upload is checked before any repeat. An account
Web Locks lease prevents two tabs from reusing one operation; browsers without
Web Locks show an explicit unsupported message and block image upload. The
composer checks current vision capability and price before submission, and
runtime checks again after Media upload before Chat admission. Exact Chat
request replay first reads the existing request; if absent, it repeats the
freshness check before POST.
Only operation UUID, file hash/type/size/dimensions and started status persist
per account for reload reconciliation; image bytes and names stay in memory.
On return, the user must select the same file. An unavailable file cannot be
resumed from browser storage. Add/remove controls freeze through preflight/send.
`useChatRuntime` keeps a Chat request ID stable after uncertain admission, and
`ChatMessage` renders saved images through the shared private-image hook.
Other unsupported tool actions remain disabled.

The Chat admission ID remains in memory: closing or reloading the tab after an
uncertain Chat POST loses that ID. Within the open chat, New/Open Chat keep the
draft and exact ID until reconciliation. Cross-tab recovery of an uncertain
Chat admission needs a separate privacy-aware design; Media upload recovery
alone does not prove whether a paid Chat request was accepted.

Nearest tests: `apps/web/e2e/chat-attachments.spec.ts` for Media upload,
reconciliation, plan rejection and persisted preview; `chat-sidebar.spec.ts`
for rail/drawer/focus; `chat-responsive.spec.ts` for viewport geometry;
`catalog.spec.ts` for model prices; `shell.spec.ts` for the shared header.

## Canonical routing

This existing Chat shell remains the frontend owner. Product behavior: `docs/PRODUCT.md`; interaction/renderer acceptance: `docs/UX.md`; branch/context/domain boundaries: `docs/ARCHITECTURE.md`; source/process rules: `docs/MAINTAINABILITY.md` and `docs/DEVELOPMENT.md`. Proposal snapshots are provenance only.

Nearest browser evidence remains `apps/web/e2e/chat-responsive.spec.ts` and `apps/web/e2e/chat-attachments.spec.ts` plus the current Chat acceptance suites. P1 converges this implementation; it does not create a parallel Chat page.

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
