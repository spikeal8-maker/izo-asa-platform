# FRONTEND-001 — independent review checklist

Status: **staging reviewer aid / no PASS recorded here**.

Frozen source under review: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.
PR: `#36`.

The repository requires a separate independent review for this high-risk package. This checklist narrows the review so it can be performed against the exact frozen source rather than the staging branch.

## Required reviewer focus

1. **Scope integrity**
   - package remains within declared `cross_domain` ceiling;
   - changed-file count is exactly the declared 40-path ceiling;
   - no hidden backend business-logic expansion is present;
   - tests/limits were not weakened to obtain green CI.

2. **Auth / permissions / ownership**
   - Account/Admin/Access security-sensitive handlers remain functionally preserved;
   - private Gallery/Media access is still owner-checked;
   - no staff privilege is inferred from UI visibility;
   - no client-side identity/permission shortcut was introduced.

3. **Paid Image safety**
   - existing Entitlements → Credits → quote → stable `operation_id` → Job → Media path is preserved;
   - quote expiry is still authoritative;
   - rejected-before-admission remains distinct from unknown submit outcome;
   - unknown response does not create a replacement paid operation;
   - provider uncertainty/reconciliation remains server-owned.

4. **Chat honesty**
   - no text-chat backend success is fabricated;
   - local user turn/unavailable notice is not represented as assistant output;
   - unsupported Video/Audio/3D runtime is not represented as completed generation.

5. **Feed honesty**
   - presentation examples are clearly examples, not fake users/publications/likes;
   - no private asset metadata is exposed through Feed shell work.

6. **CSP / edge change**
   - any Gallery `blob:` allowance is bounded to the intended private preview requirement;
   - no unrelated security directive was relaxed.

7. **Design-system boundaries**
   - semantic color v1.1 is centralized through tokens;
   - no per-workspace decorative color system was reintroduced;
   - shell/navigation split improves ownership rather than creating another monolith.

8. **Responsive evidence**
   - exact-head browser evidence is bound to the same source SHA;
   - no full-page horizontal overflow regressions are hidden by screenshot-only checks;
   - phone/tablet/desktop/QHD/UHD/HiDPI coverage is actually executed by CI.

## Known product mismatch that is not a hidden review failure

The current frozen Chat composer still contains a visible manual `Инструменты` workspace picker. UX v4 identifies this as a follow-up product mismatch, not as evidence that the existing backend/security implementation is unsafe.

Reviewer should verify that this mismatch is presentation-only and does not bypass Jobs/Credits/Media contracts. Whether FRONTEND-001 is visually accepted with that follow-up is an owner decision, not an independent-review substitution.

## Evidence to consult

- PR #36 exact head and diff;
- `docs/reviews/FRONTEND-001.md` on the frozen source;
- required workflow runs for the frozen SHA;
- `tools/scopes/frontend-001.json`;
- `apps/web/AGENTS.md` and touched feature READMEs;
- targeted source around Chat, Studio, Gallery, Account/Admin/Access;
- browser-evidence artifact only as supplemental presentation evidence.

Do not review or approve `docs/ux-spec-v4-staging` as if it were part of FRONTEND-001. It is a separate non-canonical staging lineage.

## Machine-enforced PASS format

Only after the independent review is actually complete, the reviewer publishes a PR conversation comment exactly matching the repository parser:

`INDEPENDENT_REVIEW PASS source=5c0e79b6fc3a7120207d0889b176fbfed3dab973 reviewer=<reviewer-id>`

Do not publish that marker from a self-review or from this checklist. `tools/review_evidence.py` intentionally requires exact-source binding.

## Self-check

This document requests and structures the review; it does not claim that the review passed.