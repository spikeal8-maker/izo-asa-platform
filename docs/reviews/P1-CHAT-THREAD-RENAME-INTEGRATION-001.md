# P1-CHAT-THREAD-RENAME-INTEGRATION-001 — bounded integration task

## Authority and status

The owner explicitly authorized updating the still-unaccepted rename PR #271 from accepted main by ordinary merge, preserving history, followed by fresh exact-source review, full required CI and a new owner waiver when an independent GitHub actor is unavailable. The controller assigned this separate integration task before its metadata and transport correction were written. No waiver for the original rename source is carried to a new HEAD.

This record describes integration and its remaining acceptance gates. It does not declare the new source accepted, authorize a successor, or change the original package scope. The metadata writer owns only this report and its companion task manifest. The REST validator correction has a separate implementer and independent reviewer.

## Exact lineage and separate scope evidence

| Evidence | Exact identity and meaning |
|---|---|
| Original package base | `27e506d27be72fa1a3054909aa82e7084f72818b`, retained in PLAN and the original rename scope |
| Reviewed rename source | `68c204b6597765ec3c146e1150b5bd4764ce7916`, tree `5073aec367cf28e340a43dcfaf45e9392960af11`, original 27 changed paths within its 32-file cap |
| Accepted tooling source | PR #270, `f75bfa2ed182622d9f56c36b7dd533d4fb69d89d`, tree `93b92f60af1c4d4138ffb056816598e8713464c4` |
| Accepted main / task base | `0182c5410ad9b536b07ff750a6fbf874694a0d74`, actual normal merge of PR #270; its required push CI passed, as recorded by the controller |
| Ordinary integration merge | `3bec5794a30435686966601e003584da02555257`, ordered parents `[68c204b6597765ec3c146e1150b5bd4764ce7916, 0182c5410ad9b536b07ff750a6fbf874694a0d74]`, tree `1285adf4fe324b66d5347541cba5652e01ab4104` |

The integration merge has the same 27 rename changes relative to accepted main as the original rename source has relative to its frozen package base. It preserves both histories without force-push, rebasing or product edits. The accepted tooling files are part of the task baseline; their acceptance does not become rename implementation evidence.

The task initially fixed 32 exact allowed paths: the 27 existing rename paths, two integration metadata files, and three paths for the reproduced REST validator correction. Those original correction paths are `tools/project_state_rest_checks.py`, `tests/test_project_state_rest_checks.py` and `docs/PROJECT_STATE_TRANSPORT.md`. Metadata alone exposes 29 changed paths relative to the task base.

Before creating any additional path, the fix implementer requested a natural ownership split: its first working REST correction measured 14,837 bytes / 237 lines, while the complete negative matrix still needed room. The independent reviewer confirmed that event/run/job/suite identity belongs in a separate bounded helper. The controller therefore approved exactly `tools/project_state_check_events.py` and `tests/test_project_state_check_events.py` before writing them, and fixed this task's finite cap at 34. Expected helper sizes are 140–190 lines / 9–11 KB and 200–270 lines / 10–12 KB respectively; actual sizes and scope must be measured at freeze. The implementer plans to restore the original REST test file byte-for-byte, which would leave 33 actual changed paths within the 34 allowed paths. Neither that result nor the final negative-matrix PASS is assumed in advance. The unchanged cross-domain class limit remains 40, risk remains high, and independent review remains mandatory. Any further path requires a new controller decision before writing.

The original rename manifest and report remain byte-identical to source `68c204b...`, including their original scope and tooling non-goal. The separately assigned integration task owns the necessary transport correction introduced by accepted main. It does not retrofit that correction into the original product package contract.

The cumulative diff from the frozen package base includes already accepted tooling and therefore exceeds the original rename cap: 45 paths at the ordinary integration merge, 47 with the two integration metadata files. Updating existing tooling paths does not add new cumulative paths; the two separately approved event helper/test files add two. This record does not call that cumulative diff a passing original stock-scope check. Stock evidence remains bound to `68c204b...`; the integration scope is checked against its distinct approved base `0182c541...`.

## Preserved state and governing contract

All four state files are inherited unchanged from the actual repository workflow used to activate rename. The metadata writer does not edit PLAN, PACKAGES, CURRENT or CHECKPOINTS; the frozen base, active package, working-branch identity and existing checkpoint records remain unchanged. The integration manifest's sensitive approvals identify those inherited workflow outputs and the migration/scope paths; they do not authorize manual state writes.

`DEVELOPMENT.md` section 3 defines an exact base and finite scope for a package/task. Section 11 permits controller integration of reviewed isolated results without new product semantics. `check_change.py` validates the explicit task base and ancestry. The existing active-package test continues to require the original rename scope base to equal PLAN's frozen base.

State workflow still loads the original active scope for its high-risk review requirement. It does not automatically select this integration manifest or prove its path count. The controller must retain the original source proof, accepted tooling proof and actual integration scope result separately, then run the unchanged exact-source CI/review/checkpoint validation. No validator or limit is bypassed to substitute one proof for another.

## Reproduced transport issue and bounded correction

The controller reproduced a REST check-history validation defect after accepted main integration. GitHub's `filter=latest` response can still contain historical checks from repeated PR events on the same commit. The current validator first rejects a cancelled historical check despite successful selected PR workflows; it also groups collected checks solely by `(name, app_id)`, which cannot distinguish separate event histories. The correction belongs to the existing REST evidence owner, not to Chat runtime or a new transport.

The fix implementer executed `python -B -m pytest -ra tests/test_project_state_rest_checks.py::test_multiple_pr_events_keep_cancelled_history_and_accept_current_checks` against the unchanged validator at baseline `0182c541...`, using a separate scratch basetemp. The result was **1 failed in 0.08 seconds**: `ValueError: REST check rollup contains foreign, pending or failed check`. Its synthetic fixture models three PR events, nine runs and twelve checks, including an older completed/cancelled verify check while the selected workflows succeed. This is a reported, reproducible regression test, not a synthetic substitute for live GitHub evidence.

The fix implementer is responsible for a failing regression, the smallest event/history identity correction and negative tests preserving real required checks, complete pagination, selected run/job/attempt identity, and refusal of relevant failed or pending checks. Its exact reproduction and executed tests must be recorded before the integrated source is frozen. No success or final fix SHA is asserted by this metadata-only commit.

## Historical verification is not new-source acceptance

Historical [Foundation CI run 39169381867](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/39169381867) completed SUCCESS at `2026-10-18T22:04:00Z`. The controller and independent QA/reviewer verified source `68c204b6597765ec3c146e1150b5bd4764ce7916`, base `0182c5410ad9b536b07ff750a6fbf874694a0d74`, tested merge `4c6b9fa731ac37a6dd938779ab782b46e4ffc8f4` and tree `1285adf4fe324b66d5347541cba5652e01ab4104`.

That run recorded Python **1320 passed, 1 skipped, 3 warnings** and browser **880 passed, 391 skipped**. All 1271 browser results used retry 0; the 80 rename/race cases passed, with no flaky outcomes or browser errors. These are historical source-68 results. They do not prove the later metadata/fix source, even where an earlier tested tree matches the ordinary integration merge. Fresh exact-head CI remains required.

Before publication/freeze, execute the task scope check against `0182c5410ad9b536b07ff750a6fbf874694a0d74`, documentation and whitespace checks, the existing scope contract tests, and byte-preservation checks. The controller must additionally verify the final canonical checkout, contracts, hygiene and the integrated correction tests. This isolated metadata branch is not itself the canonical working branch.

After publication, required PR workflows, the full tested-merge identity, independent exact-source review or a new explicit owner waiver, and normal merge remain mandatory. The subsequent source checkpoint must name the new published PR head. The old rename source remains implementation provenance and is not substituted for that new checkpoint source. Terminal closeout and successor activation remain separate state-workflow steps.

## Maintenance delta and self-review

This writing task creates one finite JSON scope and one historical review report. It changes no handwritten production/test/tool owner, no live domain README, no context map, no dependency and no generated artifact. The metadata introduces no runtime dependency or new default-context content. The original report and all state files remain untouched.

The initial 32-file integration limit and the later exact two-path split were assigned explicitly before their respective writes. The 34-file task cap records that ownership decision; no scope failure or hard-limit relaxation was used to obtain PASS. Accepted tooling remains in the baseline, and all five possible correction paths are explicit. The metadata-only measurements and executed checks below describe its original commit; the integrated source requires fresh measurements and checks. The metadata self-review does not stand in for the correction's tests or the independent final integration review.

Observed metadata sizes: scope 3306 bytes / 69 lines; report 10852 bytes / 71 lines. Handwritten code growth and live-domain Markdown growth are both zero. This report is historical evidence under `docs/reviews`, outside default agent context; neither new file is a handwritten code owner approaching its warning budget.

### Metadata-only verification

Executed on Python 3.13.16 before this metadata commit:

- `check_change.py --base 0182c5410ad9b536b07ff750a6fbf874694a0d74 --scope tools/scopes/p1-chat-thread-rename-integration-001.json`: PASS, **29/32** changed files, no outside-scope or unapproved-sensitive paths. The three correction paths are explicitly reserved and have not been edited by this writer.
- `python -B -m pytest tests/test_change_scope.py -o addopts='' -p no:cacheprovider -q`, with a scratch basetemp: **23 passed in 0.06 seconds**. The original active-package base contract is preserved.
- `check_docs.py` and staged `git diff --check`: PASS.
- `project_state.py verify` on the isolated `docs/rename-integration-contract` branch: expected exit 2, because it is not PLAN's canonical working branch. No branch or state was changed to suppress that result.
- The supported read-only `project_state.py --repo-root` verification of the controller's canonical checkout: **PROJECT STATE OK**. Final integrated-source verification remains the controller's responsibility.

The preservation check confirmed all 27 stock rename blobs match `68c204b...`, including the four state files and original manifest/report. It also confirmed the three fix-owner files still match accepted base `0182c541...`. The metadata check does not execute the pending REST correction tests or new GitHub CI. Result: metadata is ready for independent integration review; the product's final acceptance remains pending.
