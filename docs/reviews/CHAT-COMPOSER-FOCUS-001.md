# CHAT-COMPOSER-FOCUS-001

## Scope and source audit

Separate bounded technical debt; this identifier does not activate a canonical package.
Base: `321fcb4fe193993db70aa705a46842e9836daac0`.
Branch: `fix/chat-composer-focus-recovery-001`.
Scope was recorded before implementation: tiny, medium risk, three paths, independent review required.

SOURCE_AUDIT_MODE: BOUNDED_LOCAL. The existing uncertain-selection test in
`apps/web/e2e/conversation-graph-races.spec.ts` owns the acceptance scenario.
Its fixture already provides a Graph-response gate. Runtime owners were inspected read-only:
`useAssistantAttempts`, `useConversationGraph`, `ChatPage`, `ChatComposer` and `useConversationLayout`.
OBSERVABLE_SEMANTICS_CHANGED=NO; OWNER_BOUNDARY_CHANGED=NO.
DONOR_RESEARCH=NOT_REQUIRED; DONOR_SHA=NOT_REQUIRED: this change makes an existing test precondition
deterministic without changing product behavior or reusing donor code.

## Finding and change

The original test called `input.focus()` while uncertain-selection recovery could temporarily disable
the textarea. It never established that deliberate focus had actually been acquired. Playwright's
[actionability table](https://playwright.dev/docs/actionability) lists no Enabled check for `locator.focus()`.

The unchanged case passed 12 local attempts across phone, tablet-landscape and laptop. A controlled
experiment then held the Graph response: all three attempts to focus the disabled composer returned
with `disabled=true`, `active=false`, and failed the original final focus assertion. In the positive
control, all three cases first acquired focus before recovery. Event logs showed focus, native blur
while disabled, and restoration to the same DOM node after recovery. This demonstrates a reachable
test-precondition race. Historical CI snapshots do not record the intervening DOM events, so they do
not independently prove the precise timing of every previous failure.

The repaired case holds the attempts response, verifies that the composer is enabled and focused,
then releases that response. It holds the subsequent Graph response long enough to verify the real
disabled interval, releases Graph, and retains the original persisted-variant, final-focus and
single-command assertions. Both gates release in `finally`, including assertion failures.
No sleeps, timeout/retry increases, skips, assertion weakening, shared-fixture or runtime changes.

## Local validation

Environment: Node 24.19.0, npm 11.9.0, Vite 8.2.4, Playwright 1.61.0, Python 3.13.16.
The isolated worktree has its own copied `node_modules`; no dependency resolver or lockfile update ran.
The available Chromium 140.0.7339.186, revision 1193, was used only for local diagnostic validation.
It is not the project's pinned Chromium 149, revision 1228; its previously blocked CDN download was
not retried. Full pinned-browser CI remains required after publication.

Scratch configurations import the unchanged repository configuration, select that available browser,
use an isolated server at `127.0.0.1:4191` with `reuseExistingServer=false`, and write JSON/trace evidence.
Test timeout remains 30 seconds, assertion timeout 5 seconds, workers 2, CLI retries 0.
Local loopback execution required approved sandbox escalation; no proxy/auth settings changed.

| Check | Actual result |
|---|---|
| `npm run build` | Exit 0; contracts generation, typecheck and bundle succeed; existing bundle-size warning remains |
| Repaired case, three repeats on each of phone/tablet-landscape/laptop | 9 passed, 0 failed, 0 skipped, 0 flaky; 8.1 seconds |
| Entire existing `conversation-graph-races.spec.ts`, same three viewports | 36 passed, 0 failed, 6 existing viewport skips, 0 flaky; 21.7 seconds |

Commands from `apps/web`:

```sh
npm run build
CI=1 node node_modules/playwright/cli.js test --config=/tmp/izo-asa-composer-focus-fix-evidence/playwright.config.ts conversation-graph-races.spec.ts --grep 'an uncertain selection reads persisted state and preserves deliberate composer focus' --project=phone --project=tablet-landscape --project=laptop --repeat-each=3 --retries=0 --trace=on
CI=1 node node_modules/playwright/cli.js test --config=/tmp/izo-asa-composer-focus-fix-evidence/spec.config.ts conversation-graph-races.spec.ts --project=phone --project=tablet-landscape --project=laptop --retries=0 --trace=on
```

Raw JSON, logs, traces and scratch configurations are in `/tmp/izo-asa-composer-focus-fix-evidence`.
The preceding controlled experiment is in `/tmp/izo-asa-composer-focus-repro/reproduction-receipt.json`,
SHA-256 `118a31ebea67439568244af782169b6a4d9c7f632ef4be88ce94e27e056c27d5`.

`project_state.py verify` returned the expected isolation diagnostic, exit 2:
checkout branch `fix/chat-composer-focus-recovery-001` differs from PLAN's
`codex/p1-chat-message-edit-001`. This is not a passing state verification. All four canonical files
remain byte-identical to the base, including all 30 existing checkpoints; no state transition ran.

## Maintainability and self-review

The only changed handwritten owner grows from 10,505 bytes / 171 lines to 11,268 bytes / 189 lines;
headroom is 4,732 bytes / 161 lines below its 16,000-byte / 350-line limits. No near-limit file grows.
The resolved `web.chat` initial route remains 8,222 bytes, root start context 4,168 bytes, and local
Chat live documentation 5,178 bytes. Owner maps and live documentation are unchanged. The three-path
scope contains one test and its manifest/report; search, dependencies, workflows and runtime are untouched.
This replaces an uncontrolled timing assumption with existing fixture gates without adding a new test owner.

SELF_REVIEW: PASS for this bounded delta. Independent review and complete required remote CI are
PENDING. Frozen source identity, final local gate receipts and subsequent CI/review outcomes belong
in the PR body; this report does not claim publication, merge or technical acceptance.
