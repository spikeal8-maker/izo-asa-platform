# DOC-004C · SELF_REVIEW

Verdict before publish: **PASS for implementation/self-review; remote CI pending**.

## Scope

Goal: close the remaining continuation-safety defects found after DOC-004B without changing product runtime.
Approved base: `fe47e208809b5950b08c7133ba922d7be5742d24`.
Working branch: `docs/continuation-safety`.
Runtime source, migrations, dependencies, OpenAPI contract and CI workflows are not changed.

## Findings fixed

1. The old `branch_from` model could start the next package from DOC-004 instead of the verified DOC-004B head.
   PLAN now separates `current_package_base`, `working_branch`, and `next_branch_source=verified_working_head`.
2. State transition trusted caller-supplied SHA/CI numbers. `begin-next` now reads the current source HEAD,
   GitHub PR head, required workflow runs, current PR merge ref and Foundation `IZO_BUILD_SHA` itself.
3. PR CI was previously described as exact-source CI. Evidence is now explicitly `pr_merge_tree`; exact-source
   is claimed only when a workflow really checks out that source commit.
4. State transition could leave a half-created branch if state writing failed. It now restores PLAN/CURRENT,
   returns to the frozen branch and deletes the incomplete branch; this failure path has a regression test.
5. `LINEAGE-001` did not depend on the maintenance layer that must precede it. It now depends on DOC-004C,
   and transition checks dependency readiness before activation.
6. Local ownership docs still contained old SHA/PR and statements such as Jobs/Media not existing.
   Historical versions were archived; current Admin/Credits/Entitlements/Media/security maps are short and current.
7. AI_RUNTIME/PRODUCT/OPERATIONS contained pre-fal/pre-Jobs status language; current broad contracts now distinguish
   implemented canonical runtime from features/live acceptance that are still pending.
8. Router counted stopwords and accumulated weak alias matches. It now normalizes common Russian stems, removes
   RU/EN stopwords, uses best-alias scoring, falls back from low-confidence blocks to routes, and has explicit
   cross-boundary ambiguity for price/cancel/refund/download-403 cases.
9. Block coverage grew from 16 to 22 stable owner/symbol/anchor locators, including Gallery controls, Credits history,
   account security/verification, Admin search and Jobs-list controls.
10. Encoding validation now includes PLAN/CONTEXT/BLOCK/corpus JSON, not Markdown only.

## Evidence before publish

- `python tools/check_docs.py` — PASS: active DOC-004C, next LINEAGE-001, 22 blocks, 15 routes.
- `python tools/project_state.py verify` — PASS.
- Routing corpus — 52 expected resolved/ambiguous/unresolved cases through `test_docs_system.py`.
- Docs/state/change-scope/web/image boundary set — **45/45 PASS** with `PYTHONUTF8=1`.
- Real read-only `fetch_pr_evidence(24, fe47e20…)` — PASS and binds Foundation CI to merge tree
  `b1c941966ea4fd53fd00322808e90adabbc28077` through the workflow log's `IZO_BUILD_SHA`.
- `npm run build` — PASS; no generated file remained changed.
- `git diff --check` — PASS.
- Scope after this report: expected **30/30**, outside scope 0, sensitive violations 0.

## Local limitation

`python tools/export_contracts.py --check` is not a valid local gate in this checkout's global Python:
installed FastAPI/Pydantic/Starlette are `0.125.0 / 2.12.5 / 0.50.0`, while the project lock requires
`0.141.1 / 2.13.4 / 1.6.0`. No contract file was regenerated and no dependency was changed to hide this.
The locked Ubuntu GitHub workflow remains the authoritative contract/full-suite gate after publish.

No merge, deploy, live fal call, real spend or independent external review is claimed by DOC-004C.
