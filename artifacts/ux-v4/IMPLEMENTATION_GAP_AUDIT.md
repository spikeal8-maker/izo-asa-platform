# IZO ASA UX v4 — аудит текущей реализации

Статус: **staging / non-canonical**. Документ не заменяет `PRODUCT.md`, `UX.md`, `ADMIN.md`, `ARCHITECTURE.md` и не меняет package state.

Проверено по `spikeal8-maker/izo-asa-platform`, ветка `ux/frontend-reset`, source head `5c0e79b6fc3a7120207d0889b176fbfed3dab973`, 2026-09-16.

## Обозначения

- **WORKING** — серверный пользовательский путь реально подключён.
- **PARTIAL** — часть пути работает, но целевой UX/функции ещё не завершены.
- **PLACEHOLDER** — есть визуальная поверхность, но реального runtime нет.
- **TARGET-ONLY** — описано продуктовым контрактом, текущего экрана/route нет.
- **CONFLICT** — текущий код, старый target-contract и новая owner-direction расходятся.

## Текущие пользовательские поверхности

| Область | Текущий route | Статус | Что реально есть сейчас | Ключевой разрыв до UX v4 |
|---|---|---:|---|---|
| Chat | `/`, `/studio/chat` | PARTIAL / CONFLICT | Chat-first shell, локальный ввод сообщений, composer, explicit notice что text runtime не подключён | Видимый `Инструменты` picker конфликтует с intent-driven Chat; нет server threads/messages/streaming/tool jobs |
| Image | `/image`, `/studio/image` | WORKING alpha | Entitlements → Credits → quote → idempotent Job submit → Jobs → Media/Gallery | Нужны source picker, styles, compose/edit/mask/outpaint и новая geometry без регресса paid-safety |
| Video | `/studio/video` | PLACEHOLDER | Только preview cards через `SectionPage` | Нет runtime/job/result; target route `/video` не введён |
| Audio | `/studio/audio` | PLACEHOLDER | Только preview cards через `SectionPage` | Нет TTS/ASR/music runtime; target route `/audio` не введён |
| 3D | `/studio/3d` | PLACEHOLDER | Только preview cards через `SectionPage` | Нет generator/manifest/viewer runtime; target route `/3d` не введён |
| Gallery | `/gallery` | PARTIAL | Private server-owned PNG assets, paging, storage counters, detail navigation | Нет multimodal cards, real thumbnails in list, delete/publish workflow, lineage UI |
| Asset detail | `/gallery/{assetId}` | PARTIAL | Route and private asset detail owner exist | Needs multimodal viewer/actions/version lineage as modalities expand |
| Jobs | `/jobs`, `/jobs/{jobId}` | WORKING | Server list/detail, polling, cancel request, unknown-provider/reconciliation states, charged/reserved credits, link to saved asset | UI can be redesigned but operational semantics must remain server-owned |
| Feed | `/feed` | PLACEHOLDER | Visual editorial grid using explicit fake examples | Нет Publication backend/list/detail/reactions/report/moderation user flow |
| Login/Register | `/login`, `/register` | WORKING/PARTIAL | Server auth; register can claim bounded guest owner | Platform login adapters and final product presentation remain later work |
| Sessions | `/account`, `/account/sessions` | WORKING | Server auth/session list and revocation | Needs final account information architecture |
| Verify/Password | `/verify-email`, `/password/forgot`, `/password/reset`, `/account/security` | WORKING/PARTIAL | Server challenges/password lifecycle; delivery is explicitly test-only | Production delivery and final UX states later |
| Connections | `/account/connections` | PARTIAL | Current email/password state only | Telegram/MAX linking/unlinking not enabled |
| Credits | `/account/credits` | WORKING surface | Existing server-backed credits owner is routed separately | Must stay separate from plan/tariff and LLM-token wording |
| Help | `/help` | PARTIAL / CONFLICT | Static `SectionPage` guidance | Text still says user selects Chat tool; conflicts with invisible routing target |
| Unknown route | fallback | WORKING basic | Safe “Страница не найдена” surface | Dedicated route/state can be refined later |

## Админка: что действительно реализовано

`App.tsx` routes every `/admin/*` path into Admin, but `AdminPage.tsx` only recognizes `/admin`, `/admin/users`, `/admin/users/{uuid}` and `/admin/audit`; `/admin/access` has a dedicated `AccessPage`. Any other admin route explicitly returns “Этот административный экран ещё не реализован.”

Therefore UX v4 must treat A-01…A-30 as **target coverage**, not current implementation. The current operational subset is users/user detail, limited credit visibility/actions in the user card, audit, and access delegation.

## Route conflicts that must be reconciled before canonical implementation

1. `PRODUCT.md` historically assigns U-01 marketing home to `/`, while current FRONTEND-001 makes `/` Chat.
2. Historical U-09 `/app` hub is not present in current router; UX v4 does not require a second creative hub.
3. Historical `/chat` and `/chat/{threadId}` contract is not current router behavior; current Chat lives at `/` plus `/studio/chat` alias.
4. Video/Audio/3D current navigation emits `/studio/video`, `/studio/audio`, `/studio/3d`, while v4 proposes concise `/video`, `/audio`, `/3d` canonical routes.
5. Historical `/paint` editor route is unresolved against an integrated Image editor mode.
6. `/studio/*` should remain compatibility-only if concise routes are accepted; feature code should not create new `/studio/*` links.

These are product decisions, not router cleanup. They must be resolved in repository-owned docs before runtime migration.

## Safety invariants that a visual rewrite must not break

- Image quote expiry and server-owned capability/size policy.
- persisted `operation_id` replay/idempotency around Job admission.
- distinction between rejection-before-admission and unknown submit outcome.
- no automatic second paid submit when provider outcome is unknown.
- server-owned Credits reserve/charge state.
- private Media ownership and authenticated asset loading.
- Jobs survive navigation/browser close and remain authoritative.
- unsupported Chat/Video/Audio/3D runtime must never be rendered as successful generation.
- public Feed examples must never be presented as real user publications.

## Canonical reconciliation candidate

When lifecycle permits a new package, the smallest safe documentation pass is:

1. `PRODUCT.md` — resolve `/`, `/app`, `/chat`, `/paint`, concise studio routes and compatibility aliases.
2. `UX.md` / `UX_PRODUCT_SHELL.md` — remove visible Chat tool-selection assumption and bind Chat/studio layout rules to accepted routes.
3. `ADMIN.md` — preserve A-01…A-30 as target registry while explicitly separating current implemented subset from future surfaces.
4. `ARCHITECTURE.md` or ADR only where a newly accepted persistent entity is required (ChatThread, VideoProject, AudioProject, editable document/version lineage).
5. local feature README/BLOCK_MAP/CONTEXT_MAP only for owners actually touched by that package.

This is a reconciliation candidate, **not a second roadmap**.

## Lifecycle gate verified before this audit

Current canonical state remains `FRONTEND-001` on `ux/frontend-reset`; package scope is high-risk and requires independent review. PR #36 remains draft/unmerged. The staging branch must not be used as `begin-next` substitute and must not be merged as canonical documentation without normal lifecycle checks.

## Self-review

PASS for the purpose of a staging audit:

- no claim that Chat text runtime works;
- no claim that Video/Audio/3D runtime exists;
- no claim that Feed is a real Publication feed;
- no claim that A-01…A-30 are currently implemented;
- current Image/Jobs safety behavior is preserved rather than redesigned in prose;
- route conflicts are marked as conflicts, not silently resolved;
- this document does not mutate `ux/frontend-reset`, `PLAN.json`, `CURRENT.md` or PR #36.
