# P1-CONVERSATION-GRAPH-001

Status: active after the genuine successor transition; implementation and package acceptance are pending.

## Goal and canonical source

Add "Ответить заново", durable response variants, selection of completed variants and execution context
from selected responses inside the existing Chat domain. The owner selected this package after rename closeout.
The accepted base is `e637017111fcea0ec4ad6291ac700f8baa90a270`, the ordinary merge of
[PR #272](https://github.com/spikeal8-maker/izo-asa-platform/pull/272).
Its ordered parents are `13c8240ed7b49028b7e479b3870aaf97e68f9654` and
`a26f74e693be7ed617bb8aed221be89cd4760876`; its tree is `69811c1a05cb552cf1fc810ee97407f5b8ac1db7`.

The narrow source audit read `ARCHITECTURE` section 10, `AI_RUNTIME` section 11, `UX` section 10,
the existing Chat owner maps, admission/execution/history code and adjacent tests.
The canonical contracts already define regeneration, immutable turns, completed-only selection and the selected context path.
This slice implements those decisions; edit-as-new-branch and a general Context Engine remain outside its boundary.

## Accepted predecessor evidence

The owner authorized only exact PR #272 source `a26f74e693be7ed617bb8aed221be89cd4760876`.
The actual [seven-line waiver](https://github.com/spikeal8-maker/izo-asa-platform/pull/272#issuecomment-6264491084)
was published and read back from `spikeal8-maker` at `2026-10-19T09:53:27Z`, before normal merge at `09:54:18Z`.
It binds the three successful PR workflows: Foundation `39226673674`, Dependency `39226673632`, Review Source `39226673818`.

New push/main checks on the actual merge passed independently:

| Gate | Actual result |
| --- | --- |
| [Foundation CI 39233532197](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/39233532197) | SUCCESS, attempt 1; verify 117997001499 and Windows 117997001855 |
| [Dependency Security 39233532168](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/39233532168) | SUCCESS, attempt 1; npm audit 117997001552 |
| Python | 1378 passed, 1 skipped, 3 warnings; 239.01 seconds |
| Browser | 880 passed, 391 skipped; 1271 unique results, every retry 0; zero extra attempts, flaky results or errors |
| Rename matrix | All 80 cases across 10 viewports passed |
| Persistence | Actual container and separate clean-preview before/down/up/after cycles; volumes retained between assertions |
| Visual review | QA, independent reviewer and controller personally viewed three new desktop/mobile PNGs; PASS |

The new browser artifact `12178751863` was downloaded and independently verified: 13,515,495 bytes,
SHA-256 `79452c7115a1ea097f43cc2cc5d09085f488b5e62c12198f74f7d20a1e8244d2`.
Full QA provenance is 46,005 bytes, SHA-256 `a6654751487230306d592fba870a7cdd31cabf650ca3eae98b5957e78fe75b93`.
The independent reviewer challenged all 22 manifest files, actual workflow/log identity, the HTML report and all three images.
The large preview archive was metadata-only for local QA; its clean execution and restart really ran in CI.
Independent post-merge verdict: APPROVE, no blocking findings. These results validate the predecessor, not the new Graph code.

## Genuine state activation

The controller fast-forwarded the preserved canonical branch to the actual accepted main; checkout and state verification passed.
The actual repository command then completed with exit 0:

```sh
python -B tools/project_state.py --github-transport connector-stdio begin-decided-next \
  --branch codex/p1-conversation-graph-001 --activate P1-CONVERSATION-GRAPH-001 \
  --goal "Regenerate answers in the existing Chat domain, persist immutable turns and response attempts, switch completed variants, and freeze request context from the selected answers while preserving ownership, history and mobile usability." \
  --depends-on P1-CHAT-THREAD-RENAME-001 --decides-next --verified-pr 272
```

The live bridge forwarded 83 fresh Connector requests, including the workflow's final mutable-evidence revalidation.
Actual output: `STATE STARTED: active=P1-CONVERSATION-GRAPH-001 branch=codex/p1-conversation-graph-001`.
The workflow wrote `PLAN.json`, `PACKAGES.json` and `CURRENT.md`; all 28 checkpoint records and the complete
`CHECKPOINTS.json` bytes remained unchanged, as did all previous package records. State verification and whitespace checks passed.
The before/after records have SHA-256 `76c0e0f748c298210028c75e1abe08fed732919ceae6d94e42f7f06ef902df84`
and `ee69c95a5dc5f550e7637011ecee468f91e0e6cd8ddcb6ff14788c402299f0ae` respectively.

## Ownership and task graph

The [finite scope](../../tools/scopes/p1-conversation-graph-001.json) is cross-domain, high risk,
38 allowed paths under the unchanged hard class limit of 40. Independent review is mandatory.

- Controller: actual state workflow, scope, this report, task contracts, integration and acceptance evidence.
- Backend implementer: 20 assigned Chat/migration/contract/test/architecture paths.
- Frontend implementer: 13 disjoint Chat UI/browser/acceptance/UX paths.
- QA: independent actual PostgreSQL, HTTP, browser and restart verification on the integrated source.
- Independent reviewer: read-only code, race, ownership, data, documentation, test and responsive review; findings return to the assigned writer.

Backend and frontend receive separate worktrees and the complete thirteen-field task contract before write GO.
Implementation precedes integration; integrated targeted gates precede source freeze, exact-head review and full required CI.
An internal technical review does not replace the separate structured GitHub approval or an authorized waiver needed for acceptance.
The owner's PR #272 waiver does not authorize merging this future feature PR.

## Agreed implementation boundary

Physical message IDs, sequences and existing message-history cursors retain their contracts.
A version marker on ThreadDetail selects an additive Graph projection with immutable turn cursors, bounded at 50 turns.
The attempt-history endpoint is bounded at 20 attempts and always includes the fresh selected turn state.
Regenerate POST includes request ID, branch, selected source attempt and expected revision; selection uses PATCH with fresh revision CAS.
Completed-only previous/next IDs and positions support the selector without loading unbounded variant history.

The old completed response remains selected while a new attempt runs or fails.
Only durable completion atomically selects the new response; selection/revision reads are coherent under PostgreSQL READ COMMITTED.
Thread-before-request row locking applies consistently to admission, claim, partial writes and completion.
Attempt lifecycle is derived from existing ChatRequest, preserving credential-disable, expiry and restart recovery behavior.
Exact request-ID replay retains idempotency; UNKNOWN outcomes block new execution until reconciliation.

Each admitted send/regenerate freezes the selected prefix; regeneration of an earlier turn excludes its alternatives and later turns.
Legacy claim snapshots have honest claim-time provenance. Forward migration retains existing IDs, messages, attachments,
manual titles and physical sequences, with same-thread foreign keys for new graph relations.
The frontend keeps stable turn DOM anchors, focus, scroll, selected chat and loaded history pages, and rejects stale revisions.
New controls remain available on keyboard, desktop and mobile using the existing design.

## Validation and maintenance delta

Graph implementation, targeted tests, integrated PostgreSQL/browser/restart gates, independent code review and its PR CI are pending.
No Graph test pass is claimed by this initial task record. Required targeted coverage includes ownership/CSRF, migration retention,
completed-only selection, stale CAS, concurrent admission/completion/selection, exact replay, UNKNOWN, selected-context snapshots,
old-turn pagination, stale browser responses, focus, mobile controls and durable selection after reload/restart.

New graph owners separate storage, commands, projection, context and UI attempt control from existing near-limit runtime files.
Local owner maps are updated when boundaries change. Hard size, line and scope limits remain unchanged.
Detailed actual commands, results, review findings and final source evidence are recorded at integration.
