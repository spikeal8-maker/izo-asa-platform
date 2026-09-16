# IZO ASA UX v4 — implementation contract

Статус: **staging / non-canonical implementation contract**. Этот документ не меняет `PLAN.json`, не открывает новый package и не разрешает менять frozen `ux/frontend-reset`.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. Цель

Зафиксировать минимальный набор правил, по которым UX v4 может быть переведён из design/staging artifact в repository-owned документацию и затем в код без регресса уже работающих Auth/Credits/Jobs/Media контрактов.

Порядок ответственности: **canonical docs → route/component ownership → UI implementation → targeted tests → full CI/visual acceptance**. Нельзя сначала переписать router/UI, а потом подгонять PRODUCT/UX под получившийся код.

## 2. Границы первой реализации

Первая реализация после штатного lifecycle transition должна быть ограничена shell/chat/document reconciliation и не включать новый backend runtime.

Разрешённый смысловой объём:

- reconcile Chat-first semantics в `PRODUCT.md`, `UX.md`, `UX_PRODUCT_SHELL.md` и implementation note в `ADMIN.md`;
- убрать из Chat постоянный ручной picker Image/Video/Audio/3D;
- оставить `+` как attachment/context entry, mic как отдельное действие и send как отправку текста;
- обновить Chat/help/navigation wording, чтобы internal capability routing не выглядел ручным меню;
- подготовить canonical/compatibility route tests только для уже принятой route map;
- сохранить current Image/Jobs/Gallery/Auth/Admin runtime semantics без backend change.

Не входит в этот объём:

- text-chat backend, durable threads/messages, streaming;
- Video/Audio/3D generation runtime;
- Feed Publication backend;
- Image masks/inpaint/outpaint/editor runtime;
- новые persistent VideoProject/AudioProject/3DDocument сущности;
- billing/provider/catalog schema changes;
- merge/deploy.

## 3. Обязательная ownership-модель

| Поверхность | Current owner | Что можно менять в shell/chat package | Что требует отдельного domain package |
|---|---|---|---|
| Product shell/routes | `apps/web/src/shell/App.tsx`, `navigation.ts`, `router.tsx`, `TopBar.tsx` | route aliases, labels, navigation semantics после docs decision | новые backend-dependent deep links/entities |
| Chat presentation | `apps/web/src/shell/ChatPage.tsx`, `chat.css` | composer geometry, attachment entry, убрать manual tool picker, honest unavailable state | ChatThread/messages/streaming/tool orchestration |
| Image Studio | `apps/web/src/features/studio/Composer.tsx`, `Studio.tsx`, `QuoteDialog.tsx` | только visual integration без изменения admission semantics | references/edit/mask/outpaint/model-catalog expansion |
| Jobs | `apps/web/src/features/studio/ResultPanel.tsx` | presentation only | lifecycle/cancel/reconcile/provider semantics |
| Gallery | `apps/web/src/features/gallery/*` | layout/cards only при сохранении owner-checked loading | delete/publish/lineage mutation contracts |
| Feed | `apps/web/src/features/feed/FeedPage.tsx` | honest placeholder/editorial presentation | Publication/reaction/report backend |
| Account/Auth | `apps/web/src/features/accounts/*` | shell/layout only | auth/session/identity semantics |
| Admin | `apps/web/src/features/admin/*` | navigation/presentation only for implemented subset | A-01…A-30 feature implementation by owning domain |

`BLOCK_MAP.json` и `CONTEXT_MAP.json` должны обновляться только для реально изменённых owners. Не добавлять broad routes/blocks заранее ради будущих экранов.

## 4. Chat contract

Chat — intent-driven surface. Пользователь формулирует задачу естественным языком. Будущий orchestrator выбирает разрешённую capability внутри backend/runtime; UI не показывает provider/model/tool routing как постоянную панель.

Target composer:

```text
[ + ]  Спросите что-нибудь...                     [mic] [send]
```

Правила:

- `+` открывает только attachment/context sources, доступные текущему runtime;
- Image/Video/Audio/3D остаются top-level workspaces;
- manual `Инструменты` button/popover из текущего `ChatPage.tsx` должен исчезнуть после canonical docs reconciliation;
- пока CHAT runtime отсутствует, submit может сохранять локальный user turn/показывать honest unavailable notice, но не assistant success;
- когда появится CHAT-001, tool execution создаёт обычный server Job и отображается typed Job/Result block;
- Chat result может иметь handoff `Открыть в студии`, но не копирует Studio settings/ledger/media ownership.

## 5. Route contract

Already confirmed/current:

- `/` — Chat home;
- `/image` — Image Studio;
- `/feed` — public Explore placeholder/current surface;
- `/gallery` — private Gallery;
- `/jobs`, `/jobs/{jobId}` — operational history/detail;
- `/account*` — account/auth surfaces;
- `/admin*` — staff surfaces subject to permissions.

Compatibility currently observed:

- `/studio/chat` → Chat surface;
- `/studio/image` → Image Studio.

Pending product decisions before implementation:

- canonical `/video`, `/audio`, `/3d` versus current `/studio/video`, `/studio/audio`, `/studio/3d`;
- `/chat/{threadId}` deep links after durable Chat backend;
- `/paint` versus integrated/nested Image editor route.

Until a decision is recorded in canonical docs, current working routes remain valid and agents must not create silent redirects.

## 6. Server-truth invariants

Visual work must preserve:

1. Entitlements determine available capability/executor/size policy.
2. Quote is authoritative for current Job admission cost and expires.
3. Submit uses stable `operation_id`; unknown response does not create a replacement operation.
4. Rejected-before-admission and unknown-after-send are distinct states.
5. Jobs own execution state; browser close/navigation does not cancel them implicitly.
6. Credits reserve/charge/release are server-owned.
7. Successful result becomes private Media/Asset under server ownership checks.
8. Provider uncertainty/reconciliation is never converted into a local fake failure/refund.
9. Unsupported Chat/Video/Audio/3D actions never show generated success.
10. Feed examples never masquerade as real publications.

## 7. Current implementation classes

- **WORKING:** Image alpha, Jobs, server Auth/session surfaces, Credits surface, core Admin users/audit/access subset.
- **PARTIAL:** Chat presentation, Gallery, Asset detail, Account IA, email/security delivery presentation, Connections.
- **PLACEHOLDER:** Video, Audio, 3D, Feed publication experience.
- **TARGET-ONLY:** most A-01…A-30 admin screens, Support/Billing/Notifications/Data export/delete and later modality runtimes.

This classification is evidence-oriented: a route entering a generic component does not make the underlying product capability implemented.

## 8. Required tests for first shell/chat implementation

Targeted minimum:

- `apps/web/e2e/shell.spec.ts` — `/` and `/studio/chat`, navigation, mobile header/bottom nav, 404;
- Chat assertion: no persistent `Инструменты` workspace picker;
- Chat assertion: no fake assistant success without runtime;
- accessible names for `+`, mic and send;
- `apps/web/e2e/studio.spec.ts` — unchanged quote → safe submit path;
- `apps/web/e2e/provider.spec.ts` — provider uncertainty/reconciliation unchanged;
- `apps/web/e2e/gallery.spec.ts` — private asset behavior unchanged;
- affected account/admin specs if shared shell changes touch them.

Before technical acceptance retain the repository viewport matrix including phone, tablet, 1440/1920, QHD/UHD/8K and HiDPI profiles already required by the active frontend contract.

## 9. Acceptance gate

Implementation is not accepted merely because screenshots look correct.

Required evidence:

- repository docs checks and project-state verification;
- scope/headroom/local-doc budget checks;
- TypeScript/Vite build;
- targeted Playwright;
- full required CI for the exact source head;
- independent review when package risk demands it;
- owner visual acceptance for the final shell on representative phone and desktop-class viewports.

No package may weaken tests, file/context budgets or security checks to make this contract pass.

## 10. Self-review

PASS as a staging implementation contract:

- no unverified backend endpoint was invented;
- current Image/Jobs safety semantics are explicitly preserved;
- unresolved routes stay unresolved;
- placeholders are separated from working features;
- future persistent entities require their own domain package/ADR;
- the document does not change canonical branch/package state.
