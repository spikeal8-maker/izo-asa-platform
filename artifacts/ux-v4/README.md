# IZO ASA UX SPEC v4 — staging artifact

This directory stores the complete UX SPEC v4 produced for `spikeal8-maker/izo-asa-platform`.

**Status:** non-canonical staging artifact. It must not be treated as a second `PRODUCT/UX/ADMIN` source of truth. Canonical reconciliation belongs in a later lifecycle package after the current frozen `FRONTEND-001` gates allow `begin-next`.

## Exact source snapshot

- repository: `spikeal8-maker/izo-asa-platform`
- source branch checked: `ux/frontend-reset`
- source head checked: `5c0e79b6fc3a7120207d0889b176fbfed3dab973`
- complete archive SHA-256: `ed4dfc898f589d4e81d3d2eb1d53086ccb0fec1ccb06a9a4126b23bbad7a3897`
- archive contains 29 files inside `IZO_ASA_UX_SPEC_V4/` plus the directory entry
- machine validation before upload: `user=45 admin=30 total=75`, VALID

## Why the full package is archived here

The repository explicitly forbids a second stable master/roadmap hierarchy. The package is therefore stored as a Git-tracked, checksum-verifiable artifact on this staging branch rather than being dropped wholesale into canonical `docs/` or into frozen PR #36.

The complete archive is preserved unchanged. The files next to it are second-pass repository-grounded review artifacts and implementation locators; they are not silently folded into canonical docs.

## Review / implementation documents

- `00_DECISION_REGISTER.md` — established/conflicting/proposed decisions.
- `00_CURRENT_API_MAP.md` — current verified Image/Jobs/Gallery API snapshot.
- `IMPLEMENTATION_GAP_AUDIT.md` — WORKING/PARTIAL/PLACEHOLDER/TARGET-ONLY/CONFLICT audit.
- `CANONICAL_RECONCILIATION_PATCHSET.md` — exact repository-owned docs that must be reconciled later.
- `IMPLEMENTATION_CONTRACT.md` — bounded implementation rules, safety invariants and required tests.
- `CURRENT_TO_TARGET_FILE_MAP.md` — current source owners/tests for each target UX change.
- `OPEN_DECISIONS.md` — only decisions that remain genuinely unresolved, with safe behavior until resolution.
- `coverage_report.md` — coverage summary for 45 user + 30 admin pages.
- `SHA256SUMS.txt` — checksums for the archived v4 source package.

## Restore

Run from this directory:

```bash
python restore_ux_v4.py
```

The script concatenates the nine Git-tracked Base64 parts, decodes the exact `tar.xz`, checks its SHA-256, and extracts the complete package. After extraction run:

```bash
cd IZO_ASA_UX_SPEC_V4
python validate_ux_spec.py
sha256sum -c SHA256SUMS.txt
```

Expected validator result: `UX SPEC VALID`, `user=45 admin=30 total=75`.

## Verification performed

The source implementation was re-read after the initial v4 package was staged. Review covered `App.tsx`, `navigation.ts`, `ChatPage.tsx`, `SectionPage.tsx`, `Composer.tsx`, `ResultPanel.tsx`, `Gallery.tsx`, `FeedPage.tsx`, `AccountPage.tsx`, `SecurityPage.tsx`, `AdminPage.tsx`, Studio local README, `BLOCK_MAP.json`, `CONTEXT_MAP.json`, `ARCHITECTURE.md`, current package state and PR #36.

The audit deliberately does not promote placeholder Video/Audio/3D/Chat runtime, prototype Feed examples or future A-01…A-30 admin surfaces to “implemented”. Route/entity disagreements are recorded as unresolved decisions rather than silently normalized.

## Promotion rule

Do not merge this staging artifact directly as canonical product documentation. Resolve open decisions, then update repository-owned `PRODUCT.md`, `UX.md`, `UX_PRODUCT_SHELL.md`, `ADMIN.md`, `ARCHITECTURE.md`/ADR as applicable in a permitted package. After docs reconciliation, modify only the mapped owners, update routing/block ownership for files actually touched, and rerun repository checks/CI on the exact source head.
