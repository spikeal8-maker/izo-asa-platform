# Chat UI ownership

`../ChatPage.tsx` owns the Chat layout and sidebar presentation state. `../chat.css` owns its grid, empty-state alignment and drawer geometry. `ChatSidebar.tsx` and `ChatSidebar.css` own history, search, compact rail and profile controls; `ChatComposer.tsx`/`ChatComposer.css` own input geometry. Keep the global header in `TopBar`, outside this feature.

Expanded/compact desktop state is a browser UI preference only. Hidden mobile history must leave the keyboard order and restore focus on dismissal or desktop-to-mobile resize. Open mobile history is a modal dialog with inert background and contained focus; dismissal clears transient search/profile state. New chat and selection close the drawer. The empty heading and composer form one layout block; narrow composer controls may use a second row.

The model picker uses the server Chat policy and informational RUB prices. UI state cannot grant permissions, publish a model, change price, select a provider key or debit Credits. Keep the policy freshness check before submit and preserve accepted-request replay behavior.

Nearest tests: `apps/web/e2e/chat-sidebar.spec.ts` for rail/drawer/focus/centering, `chat-responsive.spec.ts` for viewport geometry, `catalog.spec.ts` for model price and admission controls, and `shell.spec.ts` for the shared header.
