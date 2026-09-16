# FRONTEND-001 exit gate before UX v4 continuation

Status: **staging gate summary**. This document does not alter PR #36, package state, or canonical docs.

Frozen source: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## Technical evidence already present

PR #36 records successful exact-head workflows for the frozen source:

- Foundation CI `34948932137` — SUCCESS;
- Dependency Security `34948932448` — SUCCESS;
- Review Source `34948932309` — SUCCESS.

The Foundation run exposes a non-expired `browser-evidence` artifact for the same head SHA. The artifact is about 8.4 MB and is the correct source for visual review rather than relying only on prose or test assertions.

PR #36 also records screenshot evidence for the Chat home across the active responsive matrix, including phone, tablet, desktop, QHD/UHD and HiDPI profiles.

## Gates still open

### 1. Owner visual acceptance

Still pending in the PR state. Technical CI does not substitute for this.

Owner review should confirm at least:

- empty desktop Chat geometry: one heading + centered composer;
- conversation state: composer docks at the bottom without covering messages;
- 260px desktop sidebar and compact top header do not feel oversized;
- 1440px header is not crowded after sidebar width is accounted for;
- mobile two-row top area and short Chat/Feed/Gallery bottom navigation are usable;
- 360/390px composer is not hidden by bottom navigation/safe area;
- light default and dark mode both follow Semantic Color System v1.1;
- Feed/Gallery/Account/Admin inherited surfaces remain acceptable under the shared shell;
- no horizontal document overflow on representative viewports.

The next UX package should not reinterpret “continue” as visual acceptance of PR #36 unless the owner explicitly accepts the current visual result.

### 2. Independent review

`FRONTEND-001` scope is `risk=high` and explicitly requires independent review. Current PR conversation contains no independent-review evidence comment.

The repository lifecycle expects an evidence comment bound to the exact frozen source SHA in the form required by `MAINTAINABILITY.md` / review tooling. A self-review by the implementation agent does not satisfy this gate.

### 3. State transition

After owner acceptance and independent review evidence are present, the next package still starts only through:

```text
python tools/project_state.py begin-next ... --verified-pr 36
```

The command verifies the exact PR/source/workflows and creates the next branch from the verified frozen head. The staging branch `docs/ux-spec-v4-staging` is not a continuation base.

## Why UX v4 preparation can continue meanwhile

Staging preparation is safe because it is isolated under `artifacts/ux-v4/` and does not mutate the frozen frontend source. It may define scopes, tests, patch manifests and decision queues, but cannot claim an active package or modify canonical runtime/docs state.

## Handoff once gate closes

The bounded candidate is already prepared in:

- `NEXT_PACKAGE_SCOPE_CANDIDATE.md`;
- `frontend-002-candidate-scope.json`;
- `FAIL_FIRST_ACCEPTANCE.md`;
- `CANONICAL_DOC_PATCH_MANIFEST.md`;
- `CHAT_PATCH_PREVIEW.md`;
- `STAGING_SELF_CHECK.md`.

The first implementation package should remain Chat/docs reconciliation only. Unresolved route migrations and new modality runtimes remain separate decisions/packages.

## Self-review

PASS: this gate summary distinguishes technical pass, owner acceptance, independent review and state transition; it does not mark any pending gate complete and does not use the staging branch as canonical lineage.