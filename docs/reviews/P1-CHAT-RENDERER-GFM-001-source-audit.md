# P1-CHAT-RENDERER-GFM-001 · SOURCE_AUDIT

Target: existing Chat at `P1-CHAT-HISTORY-PAGING-001` source HEAD
`2ffe340c5ae735433d8f31e0703193ce98f88dc8`.

- Canonical target: `docs/PRODUCT.md` P1 Conversation Experience and
  `docs/UX.md` Chat v4 renderer require safe GFM tables and task lists, bounded
  horizontal overflow, and stable partial/final rendering on desktop and phone.
- Current target: `ChatMessage.tsx` uses `react-markdown` without GFM, so pipe
  tables and task markers remain plain text. `ChatRuntime.css` bounds code
  blocks; table-specific overflow is absent. The same component already blocks
  raw HTML and external Markdown image fetches and restricts link protocols.
- Nearest tests: Chat browser suites under `apps/web/e2e/`; a focused renderer
  case must cover desktop/phone geometry, unsafe content, and partial/final
  display. No backend or generated API contract changes are needed.
- Donor: not needed. Canonical target and current component define this bounded
  rendering behavior; no undefined product semantics require a benchmark.

Slice: add GFM parsing and a keyboard-scrollable table region within existing
message bounds. Preserve current safety restrictions. Math, highlighting,
message actions, branch/attempt, Context Engine, provider control, and P4 remain
outside this slice.

The integration PR also carries the accepted history-paging state transition,
the independently reviewed merged-source evidence fix, and the independently
reviewed lockfile security patch required after PR #257 merged.
