# DOC-004D · SELF_REVIEW

Package: Final Guardrails. Base/frozen source: `e676be04d52dc998072a7779e83b6a78ddd5f601`. Working branch: `docs/final-guardrails`.

## Scope

- state-machine guards only; no runtime product behavior;
- replace stale Accounts local map, preserve old version in history;
- explicit UTF-8 reads in boundary tests for Windows agents;
- four routing edge cases using existing owners;
- tighten local-map context budget from 10 KB to 5 KB.

## Findings fixed

- completed packages can no longer be supplied as a new `--next`;
- planned-next/activation must directly depend on the current finishing/active package;
- an unrelated planned package cannot be silently promoted to `planned_next`;
- stale Accounts claims about demo Gallery and missing Credits/Media/Jobs were removed;
- every `tests/*boundaries.py` `read_text()` now specifies UTF-8;
- password-field/admin-search/gallery-list/update phrasing resolves without broad search.

## Non-goals / residual risk

- no merge/deploy/live provider call;
- no runtime/UI implementation changes;
- known UHD Gallery preview E2E flake from the previous Foundation run is not modified here and must remain a separate test-stability item;
- GitHub full CI remains the authoritative final gate.

## Local evidence

- docs checker and project-state verify: PASS;
- adversarial transition checks: completed-next, missing-active-dependency and unrelated-next all REJECTED;
- boundary suite passes without `PYTHONUTF8=1` after explicit encoding changes;
- routing corpus includes the four newly found natural-language cases;
- diff/scope guard must pass before commit.

Verdict: **SELF_REVIEW PASS · FULL GITHUB CI PENDING**.
