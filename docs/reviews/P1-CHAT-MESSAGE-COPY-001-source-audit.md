# P1-CHAT-MESSAGE-COPY-001 · source audit

- Canonical target: `docs/UX.md` Messages requires assistant Copy and Copy Markdown, user Copy, and code-block exact source. Whole-answer Copy serializes the normalized message model rather than rendered DOM.
- Current owner: `apps/web/src/shell/chat/ChatMessage.tsx` renders saved `MessageView.content` with `react-markdown` and GFM. Code blocks have their own Copy. Whole-message actions are absent. `ChatRenderer.css` owns renderer presentation.
- Data contract: saved assistant `content` is Markdown, saved user `content` is plain text. Partial assistant content is updated by the same runtime and final content is restored on reload.
- Bounded slice: parse assistant content with the renderer's Markdown/GFM grammar to deterministic visible plain text for Copy; write exact content for Copy Markdown and user Copy. Keep each message's controls and clipboard feedback accessible. No DOM scraping or provider call.
- Risk and acceptance: lists, tables, links, code, raw HTML, clipboard denial, reload, and phone/laptop behavior. `chat-message-actions.spec.ts` checks these nearest browser cases. Existing safe link/raw HTML renderer and code Copy remain unchanged.
- Non-goals: edit/regenerate/branch/attempt, Context Engine, backend, Admin/BYOK/P4, and live provider behavior.
