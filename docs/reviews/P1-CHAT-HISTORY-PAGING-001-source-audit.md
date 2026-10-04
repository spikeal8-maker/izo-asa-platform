# P1-CHAT-HISTORY-PAGING-001 · SOURCE_AUDIT

Mode: FULL. Target: `spikeal8-maker/izo-asa-platform@dc31a725f97281537e0c718a56d8fd4dc8804433`.

- Canonical target: `docs/PRODUCT.md` U-15/U-16 requires owned dialog history;
  `docs/UX.md` requires stable viewport during history loading on phone and
  desktop; `docs/ARCHITECTURE.md` makes persisted server state authoritative.
- Current target: `apps/api/izo/chat/conversations.py` returned only the latest
  100 messages. `chat_messages` has unique `(thread_id, sequence)` and monotonic
  sequence. `apps/web/src/shell/chat/useThreadSelection.ts` replaced messages on
  open; `useChatScroll.ts` preserved thread-switch positions but had no prepend
  anchor. Nearest tests: `tests/test_chat.py`, `tests/test_chat_http.py`,
  `apps/web/e2e/chat-scroll.spec.ts`.
- Approved target contracts: the canonical owners above; no separate approved
  cursor format or donor-derived behavior exists.
- Applicable donor: `spikeal8-maker/IZO_ASA@126d276ef1a9fc09935125203288c013627457ed`
  was previously inspected for bounded history behavior. Its `list_threads`
  bound of 50 and `list_messages` single page of 200 have no older-message
  cursor. Classification: **REJECT** for paging semantics; no source copied.
- External benchmark: not required for this bounded interaction. The target
  already requires access to older history and viewport preservation. No new
  product decision is needed.

Implementation scope: account-scoped exclusive `before_sequence` keyset pages,
bounded 100-message responses, a visible older-message action, deduplication,
stale-selection rejection and scroll anchoring. Excludes thread-list pagination,
branch/attempt, Context Engine, renderer/actions and P4 provider/Admin semantics.

Risk classification: **medium**. This package changes account-owned Chat history pagination and viewport behavior but does not change auth, permissions, Credits/financial semantics, migrations, paid-provider lifecycle, credentials/secrets, cross-account access or release/network policy. cross_domain describes bounded file/domain span, not a security risk class. Separate read-only review remains useful quality evidence but is not a mandatory high-risk GitHub approval gate.
