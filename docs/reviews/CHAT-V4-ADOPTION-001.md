# CHAT-V4-ADOPTION-001 · E0 canonical adoption

Status: active E0 evidence; documentation/governance only.

## Source audit

```text
SOURCE_AUDIT_MODE
FULL

TARGET_REPO
spikeal8-maker/izo-asa-platform

TARGET_BASE_SHA
2a2995ee47c8c369b512c1328f02d3eb662775a3

E0_START_SHA
a386d9619be4456a962f6aab92fba5ec59e692a3

APPROVED_SPEC_SHA
11107acc164a53f81f83868b4f6d88b321328d5f

DONOR_REPO
spikeal8-maker/IZO_ASA

DONOR_SHA
2fcaa27c2f20f78d59a26de3686bccb676614b51
```

Target canonical owners: PRODUCT, UX, ARCHITECTURE, AI_RUNTIME, ADMIN,
MAINTAINABILITY, DOCS_SYSTEM, DEVELOPMENT and canonical Chat priority issue #222.
### Existing target first

The target already contains working owners; E0 does not describe a greenfield rewrite.

- Chat: `apps/api/izo/chat/*`, `apps/web/src/shell/chat/*`, `tests/test_chat*`.
- Admin: `apps/api/izo/admin/*`, `apps/web/src/features/admin/*`, `tests/test_admin*`.
- Media/Gallery: `apps/api/izo/media/*`, `apps/web/src/features/gallery/*`, Media tests.
- Accounts/Credits/Jobs: existing domain packages and their boundary/lifecycle tests.
- Image/Studio: `apps/web/src/features/studio/*` plus shared Jobs/Media runtime.

Future P1 therefore converges/improves the existing Chat; it is not permission to rewrite Chat from zero.

### Donor audit

Fresh donor evidence exists for all required product areas.

- Admin: `docs/admin-panel-guide.md`, `docs/context/admin-control-center.md`,
  `frontend/src/AdminApp.tsx`, admin modules and admin tests.
- Image: `docs/phone-image-implementation-20260824.md`,
  `docs/context/image-generation.md`, `frontend/src/phone/features/image/*`,
  generation/image tests.
- Gallery: `docs/gallery-current-product-plan.md`,
  `backend/app/services/gallery_*.py`, gallery characterization/service tests.
- Feed: `docs/feed-current-product-plan.md`,
  `docs/feed-v3-implementation-20260717.md`, `backend/app/services/feed_*.py`,
  feed characterization/service tests.
### Donor classifications and conflicts

- Product/UX/test ideas that agree with the target: `ADOPT_BEHAVIOR` / `PORT_TEST`.
- Safe reusable asset only after provenance/license/ownership review: `PORT_ASSET`.
- Legacy feature idea with incompatible implementation ownership: `REIMPLEMENT`.
- Legacy behavior conflicting with approved target: `REJECT`.
- Gallery silent tariff auto-eviction is explicitly `REJECT`; target storage exhaustion
  blocks new bytes and never silently removes already saved allowed work.
- Donor auth/session, ledger, provider secrets, storage ownership and migrations are
  not copied automatically. Wholesale feature copy is forbidden.
- Existing target implementation and approved target contracts outrank donor behavior.

### External benchmark references

Checked 2026-09-29. External products are research references, never live authority.

- ChatGPT: OpenAI Help Center, Projects in ChatGPT:
  https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- ChatGPT: OpenAI Help Center, ChatGPT capabilities overview:
  https://help.openai.com/en/articles/9260256-chatgpt-capabilities-overview
- Claude: Claude Help Center, What are projects?:
  https://support.claude.com/en/articles/9517075-what-are-projects
- Claude: Claude Help Center, What are artifacts and how do I use them?:
  https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them
E0 does not choose a new unresolved Chat interaction from these references.
It canonicalizes the rule that a future substantial user-visible Chat behavior
not fully resolved by IZO ASA sources must compare both current ChatGPT and
current Claude, record the dated evidence and rationale, then write the chosen
behavior into the IZO ASA canonical contract.

### Conflicts

1. Existing PRODUCT text says old IZO_ASA is only an explicitly requested reference.
   Approved Source-First requires applicable Admin/Image/Gallery/Feed product/domain
   work to perform a FULL donor audit. E0 replaces the conflicting process statement.
2. Issue #222 and several functional issues still use text-only D1-D4 sequencing
   where attachments/multimodal work follows text V1. Approved Chat v4 uses P1-P5,
   with P2 multimodal before `CHAT_PRODUCT_V1_ACCEPTED`. #222 must become the
   canonical P1-P5 priority; functional owners retain details but defer sequencing to #222.
3. Donor Gallery silent auto-eviction conflicts with target PRODUCT and remains rejected.

NEW_DECISIONS_REQUIRED: none.

IMPLEMENTATION_SCOPE: canonical docs, approved proposal provenance, package evidence,
canonical Chat issue routing and only contradictory functional-issue routing notes.
No product runtime, migration, provider, Credits, Media or Jobs implementation changes.

## Requirement adoption evidence

The final E0 self-review appends the independently counted Chat 193/193 and
Platform 35/35 adoption proof, orphan/owner checks, issue verification and exact-head checks.

## Requirement adoption result

Independent machine recount after canonical edits:

```text
CHAT_MUST
193

CHAT_ADOPTED
193/193

PLATFORM_MUST
35

PLATFORM_ADOPTED
35/35

ORPHAN
0

UNRESOLVED_OWNER
0

DUPLICATE_REQUIREMENT_MAPPING
0
```

Every Chat MUST appears exactly once in the adoption traceability table with non-empty canonical authority, owner, gate and evidence class; every row is `ADOPTED`. Every Platform MUST is covered exactly once by the platform traceability table with owner/evidence and `ADOPTED`.

`ADOPTED` means documentation authority was canonicalized in E0. It does not mean runtime `IMPLEMENTED`, `TESTED` or product-gate `PASS`.
## Canonical issue synchronization evidence

Repository docs self-review passed before issue mutations. Issues were then mutated and fetched back.

```text
#222
OPEN
CHAT-PRODUCT-V4 · canonical P1–P5 Chat Product V1 priority
single canonical Chat product priority

#43
OPEN
functional owner retained
E0 P1–P5 supersession note present

#87
OPEN
Conversation Graph persistence and request identity
E0 P1–P5 supersession note present

#88
OPEN
streaming, context and durable execution lifecycle
E0 P1–P5 supersession note present
```
```text
#139
OPEN
Chat shell, history and conversation actions
E0 P1–P5 supersession note present

#140
OPEN
renderer, rich message blocks and safe presentation
E0 P1–P5 supersession note present

#141
OPEN
composer, model selection, attachments and ASR interaction
E0 P1–P5 supersession note present
```

Functional issue bodies remain the owners of their detailed work. Their old D1–D4 / `TEXT_CHAT_V1_ACCEPTED` sequencing and “multimodal after text V1” statements are explicitly historical where they conflict with #222. No issue was closed and no implementation status was fabricated.
## E0 repository self-review evidence

Before issue mutation:

- `python tools/project_state.py verify` → `PROJECT STATE OK`;
- `python tools/check_docs.py` → `DOCS CHECK OK`;
- `python -m pytest -q tests/test_docs_system.py` → 10/10 PASS;
- `git diff --check` → PASS after removing new trailing whitespace;
- `AGENTS.md + docs/CURRENT.md` = 5972 bytes, hard budget 6000;
- `docs.system` initial route = 13645 bytes, hard budget 18000;
- `python tools/check_change.py --base a386d9619be4456a962f6aab92fba5ec59e692a3 --scope tools/scopes/chat-v4-adoption-001.json` → scope 20/20 PASS;
- requirement coverage → Chat 193/193, Platform 35/35, missing/orphan/duplicate 0;
- traceability owner/status sanity → unresolved owner 0.

Runtime code, migrations, provider runtime, Credits, Media and Jobs runtime are outside the E0 scope and unchanged.

## Final SELF_REVIEW

```text
SOURCE_FIRST
PASS

EXISTING_TARGET_FIRST
PASS

DONOR_POLICY
PASS

CHATGPT_CLAUDE_BENCHMARK
PASS

CHATGPT_AND_CLAUDE_BOTH_REQUIRED
PASS

EXTERNAL_PRODUCTS_NOT_AUTHORITY
PASS

CHAT_P1_P5
PASS

ADMIN_A1_A2_A3
PASS

CHAT_FIRST_SEQUENCE
PASS

VISIBLE_FUNCTIONAL_ACCEPTED
PASS

CONTROLLER_SUBAGENT_CONTRACT
PASS

ONE_WRITER_PER_PATH
PASS

DISJOINT_PARALLELISM
PASS

SUBAGENT_SCOPE_GATE
PASS

STATE_CONTROLLER_ONLY
PASS

REVIEWER_READ_ONLY
PASS

CHAT_MUST
193

CHAT_ADOPTED
193/193

PLATFORM_MUST
35

PLATFORM_ADOPTED
35/35

ORPHAN
0

UNRESOLVED_OWNER
0

DUPLICATE_NORMATIVE_OWNER
0

RUNTIME_CHANGED
NO

P1_STARTED
NO

SELF_REVIEW
PASS
```

The E0 diff has exactly 20 repository paths and contains no product runtime file. Controller/subagent process has one canonical owner (`DEVELOPMENT.md`); Source-First/benchmark trigger has one process-policy owner (`MAINTAINABILITY.md`); benchmark execution procedure lives in `DEVELOPMENT.md`; Product only states the product-quality goal. Proposal files are provenance snapshots, not live duplicate owners.
