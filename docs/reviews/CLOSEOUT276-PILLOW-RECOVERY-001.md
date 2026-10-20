# CLOSEOUT276-PILLOW-RECOVERY-001

## Purpose and boundary

Repair the runtime dependency audit after accepted PR #276 without changing
the completed `P1-CHAT-MESSAGE-EDIT-001` package or activating its successor.
This task identifier is not a new canonical package.

Base: `a6a95ef66f8cf92b65588fa07c1f7b3557b314dc`.
Branch: `fix/pillow-security-closeout-276`.
The controller owns the finite
[scope manifest](../../tools/scopes/closeout276-pillow-recovery-001.json):
five allowed paths, `tiny`, `risk=high`, independent review required.

Actual-main [Dependency Security run 39510622309](https://github.com/spikeal8-maker/izo-asa-platform/actions/runs/39510622309)
failed in the pinned Python runtime audit. Its JSON identified eight findings
in Pillow 12.3.0, each specifying 13.0.0 as a fixed version:

| Advisory | Alias |
| --- | --- |
| CVE-2026-112895 | GHSA-p4wg-p73j-c528 |
| CVE-2026-112400 | GHSA-65qm-jvmh-6pqg |
| CVE-2026-112397 | GHSA-58r4-6rv3-gfh8 |
| CVE-2026-112896 | GHSA-pchr-8j38-3x4p |
| CVE-2026-112897 | GHSA-q45j-58j2-45rg |
| CVE-2026-112395 | GHSA-462x-pgg6-55fp |
| CVE-2026-112404 | GHSA-c6hw-5grf-ff96 |
| CVE-2026-112899 | GHSA-vx6w-vv9f-6gvg |

The received failing audit JSON has SHA-256
`837ef36d6bf2bc64a3c94ee7a3eac54bf9eadeda3cd440f0c590fdde9c7d6f58`.
The official [Pillow 13.0.0 release notes](https://pillow.readthedocs.io/en/latest/releasenotes/13.0.0.html)
and [upstream release list](https://github.com/python-pillow/Pillow/releases)
confirm the released 2026-10-16 version. The repair uses that release, not an
unreleased branch or an advisory ignore.

## Source audit and implementation

`SOURCE_AUDIT_MODE: FULL` for the dependency security repair, confined to the
affected existing owners. `OBSERVABLE_SEMANTICS_CHANGED=NO` and
`OWNER_BOUNDARY_CHANGED=NO` describe the application contract: accepted image
formats, normalization, access and resource limits are preserved. Upstream
security defects are addressed by the dependency update.

The canonical target owners are `apps/api/izo/media/AGENTS.md`, its local
README, `codec.py`, and the diagnostic image worker in `jobs/worker.py`.
The initial natural-language context query did not resolve; the documented
`api.media` route resolved explicitly with 4,537 initial route bytes. Source
inspection and nearest tests covered real child decoding, upload/download
ownership, HTTP boundaries and job output finalization. Dependency audit
authority remains `.github/workflows/dependency-audit.yml`.

The applicable external implementation source is the official Pillow release.
No application donor code or behavior is reused; the Media-specific agent
instruction excludes reading the old IZO_ASA project for a single upload fix.
No new product, authorization, pricing or storage decision is introduced.

The implementation changes only four existing version literals:

- `requirements.in`: Pillow 12.3.0 to 13.0.0.
- `requirements.lock`: the same exact pin; every other runtime pin is unchanged.
- `tests/test_media_boundaries.py`: both explicit pinned-version assertions
  remain present and now require 13.0.0.

The codec still accepts PNG/JPEG/WebP and writes a clean PNG after verification,
loading, EXIF orientation and RGBA normalization. Input, output, pixel, PNG text,
CPU, address-space, process-slot and wall-clock limits are unchanged. The
diagnostic worker still uses `Image.new`, `ImageDraw.text` and PNG output.
Assertions remain equally strict; only their expected pinned version changes.
No runtime code, CI step, timeout, retry or ignore changed.

## Actual environment and dependency audit

Tests use a new private venv with Python 3.13.16, Pillow 13.0.0 and pytest 9.0.2.
All 33 installed runtime versions match the exact lock; `pip check` returned
exit 0 with no broken requirements. JPEG, WebP and zlib support are available.
Pinned test dependencies were installed from `requirements-dev.txt`; the shared
controller venv was not modified. A separate private audit venv contains
`pip-audit==2.10.1`.

The default sandbox blocked the package proxy connection. The same package
installs then succeeded through approved sandbox escalation; proxy settings and
authentication were not changed.

The exact existing CI audit command was executed without vulnerability ignores:

```sh
python -m pip_audit --disable-pip --no-deps --progress-spinner off -r requirements.lock --format json
```

At `2026-10-20T22:58:51Z`, the receipt records exit 0, 33 audited dependencies
and **zero known vulnerabilities**. The tool emitted its standard advice about
hashing pinned dependencies; the command and audit policy remain identical to
CI. This is an observed advisory database result, not a claim that no unknown
vulnerability can exist.

| Evidence identity | SHA-256 |
| --- | --- |
| Repaired `requirements.lock` | `d2d765f1bebe5c27894c3cdd5ab260d1dc108be15b890c0aa0782f523943ac8a` |
| Successful audit JSON, 1,905 bytes | `3fdb2c1b2fdd4e6aa4a1b1d6c442e0ae5c92700effe0211460bd2d1e7dcfa390` |

## Compatibility verification

Independent real-child compatibility smoke passed both cases with the installed
13.0.0 and the unchanged production decoder:

- JPEG EXIF orientation 6 rotated a 16 by 10 image to 10 by 16, preserving the
  expected color positions and producing metadata-free RGBA PNG.
- RGBA PNG preserved every channel byte exactly across alpha values 0, 1, 64,
  127, 254 and 255, while removing metadata.

The smoke used two synthetic fixtures and a 64 KiB output bound, with all normal
child limits intact. Its initial scratch harness import failed before testing;
only that harness was corrected, not application code. The successful script
SHA-256 is `46430d47739bbc0b267cfb9d916e4fcae335cd5740e5c76bd6cd6c626f88aa3e`.

The first targeted pytest invocation completed 64 cases, then stalled entering
the first media HTTP `TestClient` fixture and was interrupted with exit 130.
It is not a suite PASS. A five-second diagnostic of bare
`TestClient(FastAPI())`, without application or Pillow calls, reproduced the
blocked AnyIO portal inside the sandbox; the identical probe passed immediately
with approved sandbox escalation. No proxy, framework, runtime or test was
changed. The same selected suite and pytest flags completed through approved
escalation: **152 passed, 0 failed, 0 skipped, 2 warnings in 58.86 seconds**,
exit 0. The two warnings concern existing Starlette/httpx and AnyIO deprecated
interfaces; none of those dependencies was changed.

The completed command used the private Python 3.13.16/Pillow 13.0.0 venv:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/izo-asa-pillow-recovery-venv/bin/python -m pytest -rA \
  --junitxml=/tmp/izo-asa-pillow-recovery-evidence/targeted-tests-escalated.xml \
  tests/test_media_codec.py tests/test_media_boundaries.py tests/test_media.py \
  tests/test_media_access.py tests/test_media_http.py tests/test_jobs.py \
  tests/test_jobs_boundaries.py tests/test_jobs_recovery.py \
  tests/test_jobs_http.py tests/test_dependency_security.py
```

The successful log SHA-256 is
`095b429d4c73de56877e1b9682bbf73793f87995d0d10597c7f453951f17d740`;
JUnit XML SHA-256 is
`2da0f1471404510ed754bdcce87b37eb953953b1a3089bae741ae7843c7d8228`.
Both are retained with the initial interrupted run, diagnostic traceback,
environment, installation and audit receipts in
`/tmp/izo-asa-pillow-recovery-evidence`. Independent smoke evidence is in
`/tmp/izo-asa-pillow-recovery-review`.

Full required remote CI is **PENDING** until publication; this targeted local
suite does not substitute for it.

## State and maintenance

All four canonical state files remain byte-identical to the accepted base,
including all 30 checkpoints. The completed package, source lineage and
`next_package=NONE` are unchanged. `project_state.py verify` returned the
expected exit 2 for the isolated repair branch versus canonical
`codex/p1-chat-message-edit-001`; this is not a PASS and was not suppressed.

| Existing changed file | Bytes before / after | Lines before / after |
| --- | --- | --- |
| `requirements.in` | 185 / 185 | 10 / 10 |
| `requirements.lock` | 655 / 655 | 34 / 34 |
| `tests/test_media_boundaries.py` | 3,734 / 3,734 | 87 / 87 |

The handwritten test uses less than one quarter of its 16 KB byte limit and
stays 263 lines below its 350-line hard limit.
No existing owner or live document grows; no route, dependency owner, runtime
API or local live-doc file is added. This report stays in `docs/reviews`, outside
default live context. The controller-created manifest is included unchanged
in the five-file commit with explicit controller authorization.

## Local completion

| Gate | Result |
| --- | --- |
| `python tools/check_docs.py` | PASS, exit 0 |
| `python tools/repository_hygiene.py --base a6a95ef66f8cf92b65588fa07c1f7b3557b314dc` | PASS, exit 0 |
| `python tools/check_change.py --base a6a95ef66f8cf92b65588fa07c1f7b3557b314dc --scope tools/scopes/closeout276-pillow-recovery-001.json` | PASS, exactly five paths, no unapproved sensitive changes |
| `python tools/export_contracts.py --check` | PASS, exit 0, Python 3.13.16 |
| `git diff --check` | PASS, exit 0 |

`SELF_REVIEW: PASS` for the bounded implementation and completed local checks.
Full required remote CI remains **PENDING** and independent review of the
published commit remains required before acceptance.

Exact final commit, independent review and required remote CI belong in the
repair PR evidence. This report grants no merge, deployment or successor
activation authority.
