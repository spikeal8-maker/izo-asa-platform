# Chat UI ownership

This shell owns Chat. Canonical behavior, interaction, branches/context and maintenance rules live in `docs/PRODUCT.md`, `UX.md`, `ARCHITECTURE.md`, `MAINTAINABILITY.md` and `DEVELOPMENT.md`; proposals are provenance only.

`../ChatPage.tsx` owns layout/sidebar state and the editor-to-scroll bridge. `../chat.css` owns grid, empty state and drawer geometry; the branch toolbar can grow with its controls. `ChatSidebar.tsx`/CSS own history/search/rail/profile. Runtime supplies an explicit sidebar props object, never its full authority. `ChatComposer.tsx`/CSS own input geometry; `TopBar` keeps the global header outside Chat. Edit and branch controls reuse theme and message-action styles.

## Selection, history and input

Expanded/compact desktop state is a UI preference. Hidden mobile history leaves keyboard order; the open drawer is modal with inert background and contained focus. Dismissal restores focus and clears search/profile state; New/Open Chat close the drawer. `App.tsx` keys Chat by account, clearing private history before paint.

`useThreadHistory` keeps unique thread rows and the loaded cursor beyond 50; account change/reload starts a fresh list. `ThreadRenameForm`/`useThreadRenameEditor` own draft, Unicode validity, save/cancel/error and focus after PATCH unlock. `useThreadHistory` updates only the confirmed title and fences earlier reads without dropping pages or the selected chat.

`useThreadSelection` owns selection identity, physical-history cursors and same-thread reopen. `useChatScroll` preserves message anchors before prepend/replacement and through image layout changes; explicit user scroll releases the anchor. Late reads cannot update another account/thread. Composer draft is preserved by same-thread branch recovery.

## Models and attachments

The picker uses server Chat policy, OpenRouter catalog and informational RUB prices. Unknown RUB remains unknown. The UI cannot grant access, publish models, change prices, choose provider keys or debit Credits. `useChatPreflight` checks catalog/price freshness; accepted UUID lookup precedes fresh admission. Keys and endpoints are never browser preferences.

`AttachmentControl` owns ordered PNG/JPEG/WebP selection, paste/drop and the five-image limit. `chatAttachments` validates bytes/dimensions and uses shared Media with stable upload UUIDs. Uncertain uploads are reconciled first. Per-account Web Locks prevent cross-tab reuse; image upload is unsupported without them. Composer validates vision/price before send; runtime validates again after upload. Add/remove freezes during submission; saved images use the shared private-image hook.

Only upload UUID, hash/type/size/dimensions and started status persist. Image bytes/names stay in memory; recovery needs the same file. Chat admission intent stays in memory: navigation preserves its exact UUID within the tab, but closing/reloading loses it. Media recovery never proves paid Chat admission. Cross-tab recovery needs a separate privacy-aware design.

## Graph, branches and Edit

`ThreadDetail.graph_version=1` selects Graph; failure is explicit. Physical APIs retain their contracts. `useConversationGraph` projects immutable turns with stable assistant turn keys and fences account/thread/branch/revision/epoch. It preserves observed terminal outcomes, including off-page attempts. Every retained range is reread at one revision before execution; a publication-time guard also detects cache growth during lifecycle lookup.

`useAssistantAttempts` owns regeneration and completed-version selection. A selected answer remains during pending/failure and changes only with server evidence. `execution_branch_id` identifies a replay's original execution; current active branch/revision are separate. Cross-branch receipts trigger coherent recovery, never old-turn insertion, reactivation or terminal SSE.

`useConversationBranches` owns bounded branch lists, CAS selection, page collection, frozen ordinary-send fences and recovery. `ChatMessageEdit` owns source-model/ordered-asset Edit admission and its form: Python-compatible strip, raw 6000-codepoint/NUL validation, unchanged rejection, save/cancel/error and exact-UUID retry. It wraps each user message from its first mount, retaining the original renderer as its first child. The Page bridge captures the existing scroll anchor before editor layout changes. Cancel focuses the visible trigger; accepted save waits for DOM settlement and respects deliberate external focus.

Pending/streaming blocks Edit and branch mutation. Thread-wide `unknown_request_id` survives metadata-only branch viewing and reload. Failed post-CAS reads preserve caches/drafts while locking new execution until explicit coherent retry; newer head/turn evidence alone cannot unlock older ranges.

Nearest tests: history/thread paging, thread-rename, attachments, sidebar, responsive, catalog and shell specs; `conversation-graph*.spec.ts` covers variants/lifecycle/paging; `chat-message-edit*.spec.ts` covers Edit, branches, normalization, focus and races. Isolated `acceptance/chat-live.mjs` runs browser/PostgreSQL proofs before and after restart using fake providers.
