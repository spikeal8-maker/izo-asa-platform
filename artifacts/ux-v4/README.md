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

The human-readable files `coverage_report.md`, `00_DECISION_REGISTER.md`, `00_CURRENT_API_MAP.md` and `SHA256SUMS.txt` are also exposed next to the archive for quick review.

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

## Promotion rule

Do not merge this staging artifact directly as canonical product documentation. Resolve route conflicts from `00_DECISION_REGISTER.md`, then update repository-owned `PRODUCT.md`, `UX.md`, `ADMIN.md`, `ARCHITECTURE.md`/ADR as applicable in a permitted package, with repo checks and CI rerun.
