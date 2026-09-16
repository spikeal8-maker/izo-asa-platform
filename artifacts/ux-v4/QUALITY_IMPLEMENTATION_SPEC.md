# IZO ASA UX v4 — качественное техническое задание

Статус: **staging implementation specification / не canonical source of truth**.

Проверено против `spikeal8-maker/izo-asa-platform`, frozen source `ux/frontend-reset@5c0e79b6fc3a7120207d0889b176fbfed3dab973`, PR #36, действующих `PRODUCT.md`, `UX.md`, `ARCHITECTURE.md`, `ADMIN.md`, `DOCS_SYSTEM.md`, `MAINTAINABILITY.md`, frontend owners и project-state tooling.

Назначение этого документа — заменить россыпь промежуточных UX-v4 заметок одним исполнимым ТЗ. После переноса принятых решений в canonical docs этот файл не должен становиться вторым постоянным PRODUCT/UX.

---

## 1. Цель продукта

IZO ASA — единая AI-платформа с пятью верхнеуровневыми творческими рабочими пространствами:

1. **Chat** — intent-driven: пользователь формулирует задачу естественным языком; внутренняя маршрутизация capability/model/provider не становится постоянным ручным меню.
2. **Image** — direct tool-driven studio для создания и редактирования изображений.
3. **Video** — direct studio для видеогенерации и дальнейших видео-инструментов по мере появления реального runtime.
4. **Audio** — direct studio для TTS/ASR/музыки/аудио-инструментов по мере появления runtime.
5. **3D** — direct studio для генерации/просмотра/экспорта 3D по мере появления runtime.

Общие платформенные поверхности:

- **Gallery** — приватные Assets пользователя;
- **Feed** — отдельные публичные Publications;
- **Jobs** — операционная история выполнения, а не галерея;
- **Account / Credits / Support / Notifications** — сервисные поверхности;
- **Admin** — staff-only поверхности с серверными permissions.

Ключевая модель:

```text
User intent
   |
   +--> Chat --------> Orchestrator/Capabilities ----+
   |                                                |
   +--> Direct Studios -----------------------------+
                                                    v
                                             Jobs / Cost
                                                    v
                                               Results
                                                    v
                                               Gallery
                                                    |
                                           optional Publish
                                                    v
                                                  Feed
```

---

## 2. Источники истины и правило документации

После canonical reconciliation каждый факт имеет одного владельца:

| Факт | Canonical owner |
|---|---|
| пользовательское поведение, routes, access, product semantics | `docs/PRODUCT.md` |
| visual/responsive/accessibility | `docs/UX.md` |
| данные, ownership, domain boundaries | `docs/ARCHITECTURE.md` / ADR |
| admin permissions/settings/surfaces | `docs/ADMIN.md` |
| providers/runtime/cost/execution | `docs/AI_RUNTIME.md` |
| текущий package/branch/dependencies | `docs/PLAN.json` + `docs/CURRENT.md` |
| exact CI evidence | `docs/CHECKPOINTS.json` |

`docs/UX_PRODUCT_SHELL.md` после переноса фактов не должен оставаться параллельным владельцем product routes. Его следует либо сократить до временной migration note, либо удалить отдельным docs change.

Coding-agent не должен читать весь UX v4 по умолчанию. Для маленькой задачи используется: `AGENTS.md -> CURRENT.md -> block/route -> local README -> owner source/test`.

---

## 3. Статусы реализации

Использовать только эти статусы:

- **CURRENT** — поведение реально существует и подтверждено кодом/тестами.
- **PARTIAL** — рабочий путь существует, но target UX/функции неполны.
- **PLACEHOLDER** — только честная presentation surface, runtime отсутствует.
- **TARGET** — требование на будущее, не текущая возможность.
- **PENDING DECISION** — нельзя реализовывать до explicit owner/canonical decision.

Не использовать цифру `75/75` как readiness. Она означает только registry completeness.

Текущий срез:

| Область | Статус | Текущее доказанное состояние |
|---|---|---|
| Chat | PARTIAL | shell/composer/local user turn + честный unavailable notice; server Chat runtime отсутствует |
| Image | CURRENT alpha | Entitlements -> Credits -> Quote -> stable operation_id -> Job -> Media/Gallery |
| Jobs | CURRENT | server list/detail/poll/cancel/reconciliation/reserved/charged/asset handoff |
| Gallery | PARTIAL | private server-owned assets и detail/download boundary |
| Feed | PLACEHOLDER | editorial examples, не реальные publications |
| Video | PLACEHOLDER | generic SectionPage, runtime отсутствует |
| Audio | PLACEHOLDER | generic SectionPage, runtime отсутствует |
| 3D | PLACEHOLDER | generic SectionPage, runtime отсутствует |
| Account/Auth | CURRENT/PARTIAL | server auth/sessions/security; часть delivery/platform identities позже |
| Admin | PARTIAL | users/user detail/audit/access subset; A-01…A-30 остаются target registry |

---

## 4. Неприкосновенные server-truth инварианты

Любая перевёрстка обязана сохранять:

1. Server Entitlements определяют доступные capabilities/executors/limits/sizes.
2. Quote — authoritative оценка перед Job admission и имеет срок жизни.
3. Submit использует server quote + stable client operation id.
4. Повтор той же logical operation безопасно replay-ит receipt; новый payload не маскируется тем же id.
5. Rejected-before-admission и unknown-after-send — разные состояния.
6. Unknown provider outcome запрещает автоматическую новую платную операцию; требуется replay/reconciliation/history.
7. Credits reserve/charge/release принадлежат серверу; UI не рассчитывает wallet сам.
8. Job state переживает закрытие вкладки/restart и остаётся операционной истиной.
9. Сохранённый результат становится private Media/Asset; browser не доверяет provider URL как постоянному user asset.
10. Ownership проверяется на каждом private read/mutation; UUID/object key не является permission.
11. Unsupported Chat/Video/Audio/3D runtime никогда не отображает fake success/progress/result.
12. Feed examples никогда не выдаются за реальные user publications/likes/authors.
13. Auth/session/CSRF/staff permissions не упрощаются ради визуального package.

Изменение любого пункта требует отдельного domain/backend package и профильных tests.

---

## 5. Информационная архитектура и routes

### 5.1 Уже установленный current contract

- `/` — Chat home в текущем frontend.
- `/image` — рабочая Image Studio.
- `/feed` — public Explore/Feed surface.
- `/gallery` — private Gallery.
- `/jobs`, `/jobs/{jobId}` — operational jobs.
- `/account*` — account/auth/security/credits.
- `/admin*` — staff surfaces при наличии permission.
- `/studio/chat` — current compatibility path к Chat.
- `/studio/image` — current compatibility path к Image.

### 5.2 Не менять без решения

Следующие решения остаются в `DECISIONS.md`:

- canonical `/video`, `/audio`, `/3d` vs `/studio/*`;
- durable `/chat/{threadId}` model;
- Image edit route (`/image/{assetId}/edit` vs `/paint`/integrated mode).

До canonical decision текущие рабочие paths сохраняются. Никаких silent redirects.

### 5.3 Route ownership

Aliases/redirects принадлежат router layer. Feature components после миграции должны генерировать только canonical URLs. Не размазывать compatibility links по feature-коду.

---

## 6. Chat — целевой UX contract

### 6.1 Назначение

Chat — минимальная conversational surface, а не dashboard инструментов.

Пользователь пишет:

- «убери фон»;
- «сделай ролик 5 секунд»;
- «озвучь этот текст»;
- «сделай 3D-модель по фото».

Будущий orchestrator сам определяет разрешённый tool/capability и перед выполнением применяет schema/ownership/entitlement/cost/consent/limit checks.

### 6.2 Composer

Target:

```text
[ + ]  Спросите что-нибудь...                      [mic] [send]
```

Правила:

- `+` = attachment/context entry, не workspace picker;
- mic = voice input action;
- send = отправка текста;
- direct Image/Video/Audio/3D доступны в global workspace navigation;
- provider/model/internal tool router не показывается постоянным меню Chat;
- ручная кнопка `Инструменты` текущего FRONTEND-001 является известным follow-up mismatch и должна быть удалена маленьким package после canonical reconciliation.

Пока server Chat attachments/runtime не существуют, `+` может быть disabled с понятным title; запрещено имитировать source picker локальными fake assets.

### 6.3 Chat states

Обязательные состояния:

- empty;
- draft/multiline;
- local submitted user turn + runtime unavailable (до CHAT backend);
- loading/streaming (после реального backend);
- partial/interrupted stream;
- tool confirmation required;
- tool queued/running;
- typed result block: text/image/video/audio/3D/file/code;
- tool failure/reconciliation;
- session expired/permission denied;
- thread not found/deleted (после durable threads).

### 6.4 Result handoff

Результат Chat не копирует Studio business logic. Он отображает server Job/Asset и может дать действие `Открыть в студии`. Gallery получает тот же Asset.

### 6.5 Geometry

Desktop:

- sidebar около 260 px для текущего shell baseline;
- compact product header около 56 px;
- chat/composer reading measure примерно 768 px;
- empty state: один heading + composer, без quick-action card wall;
- conversation state: composer dock снизу, не перекрывает messages.

Phone:

- компактная верхняя область;
- creative modes остаются доступными;
- короткая bottom navigation Chat/Feed/Gallery;
- composer учитывает safe-area и keyboard viewport;
- primary actions не требуют hover.

---

## 7. Image Studio — ближайший рабочий domain

Image уже имеет реальный server flow; UX может меняться без переписывания admission semantics.

### 7.1 Current обязательный путь

```text
Auth/Guest
 -> Entitlements
 -> Credits
 -> Prompt + Capability + Size
 -> Quote
 -> Confirm
 -> stable operation_id
 -> Job
 -> Job state/reconciliation
 -> Asset
 -> Gallery
```

### 7.2 Target layout

Desktop использовать пространство для результата, а не превращать Studio в длинную форму:

```text
+----------------------+--------------------------------------+
| Composer / controls  | Preview / result                     |
| prompt               |                                      |
| source(s)            |            dominant canvas           |
| model/capability     |                                      |
| size/aspect          |                                      |
| quote/action         |                                      |
+----------------------+--------------------------------------+
| history / variants / handoff (когда реально существуют)     |
+-------------------------------------------------------------+
```

Phone — последовательный flow: source/prompt -> critical parameters -> price/submit -> result -> actions. Не копировать desktop columns в узкий экран.

### 7.3 Следующие Image capabilities

Каждая capability вводится только если backend contract существует:

- image-to-image / references;
- multi-image compose;
- mask/inpaint;
- outpaint;
- background removal;
- style/reference controls;
- owned-asset editor.

Исходный Asset не перезаписывается молча. Edit/variation создаёт derived result или explicit document revision, если такой domain object введён отдельным ADR/package.

---

## 8. Jobs, Gallery и Feed

### Jobs

Назначение: execution truth.

Показывать реальные server states, включая active/reconciling/provider unknown/deadline/auth-required/cancel requested/terminal. Процент не выдумывать.

### Gallery

Назначение: private persisted results.

Target:

- multimodal grid/list;
- type/filter/sort/pagination;
- owner-checked preview/detail/download;
- handoff в соответствующую Studio;
- delete/publish только через реальные server commands;
- lineage только если relation присутствует в API.

Не загружать full original на каждую grid-card.

### Feed

Publication — отдельный public object, а не «Asset стал публичным целиком».

До FEED backend разрешены только явно presentation examples без fake user identity/social counters. После backend: publication detail, moderation/report/reaction и privacy-safe public derivatives.

---

## 9. Video / Audio / 3D — ранний scope без выдуманных редакторов

До появления domain/runtime contracts UX описывает только outcome/state/resource boundaries.

### Video first release

Минимум:

- text/image/reference input по поддержанным capabilities;
- duration/aspect/size только из server policy;
- quote/cost;
- Job lifecycle;
- poster + player/full file readiness;
- save Asset/download/reuse.

Persistent timeline/VideoProject не является обязательным первым релизом.

### Audio first release

Минимум:

- upload/record;
- TTS;
- ASR;
- playback;
- transcript;
- music/effects только при реальном capability;
- save/export Asset.

Multitrack DAW/AudioProject не является первым обязательным release.

### 3D first release

Минимум:

```text
Text/Image -> Job -> validated 3D manifest -> poster -> on-demand viewer -> download/export
```

Viewer должен иметь resource fallback; слабое устройство может остаться на poster/download. Scene/material editor и тем более CAD — отдельные будущие решения.

---

## 10. Account и Admin

### Account

Не менять server auth/session semantics визуальным package.

Обязательные UX состояния: login/register/loading/invalid/rate limit/session limit/email verification/recovery/session list/revoke/re-auth/security errors.

Telegram/MAX identity считается доверенной только после backend verification соответствующего platform proof.

### Admin

A-01…A-30 — target registry, не текущая реализация.

Current working subset: user search/detail, audit, access delegation и связанные разрешённые credit actions.

Новый admin screen появляется только вместе с:

- domain/API owner;
- permission contract;
- local README/route locator;
- negative authorization tests;
- audit semantics.

Нельзя создавать 30 пустых route components для «coverage».

---

## 11. Design system

Semantic Color System v1.1 сохраняется:

- neutral UI + один violet brand accent;
- success/warning/error только system state;
- нет декоративного цвета по modality;
- generated content не ограничивается UI palette.

Общие UI primitives извлекать только после второго реального потребителя. Conceptual shared component в ТЗ сам по себе не основание создавать abstraction.

Предпочтительные shared candidates после фактического повторения:

- source/asset picker;
- capability/model picker;
- quote/confirm frame;
- job status;
- media viewer shell;
- admin list/detail shell.

Business logic остаётся у domain owners.

---

## 12. Responsive / accessibility acceptance

Обязательные automated CSS viewport checks:

- 360×800;
- 390×844;
- 768×1024;
- 1024×768;
- 1440×900;
- 1920×1080;
- 2560×1440;
- 3840×2160;
- HiDPI profiles, уже принятые frontend contract.

Дополнительно реальные manual checks Windows scaling 125/150/200% там, где layout критичен.

Обязательные правила:

- нет document-level horizontal overflow;
- keyboard focus видим;
- icon-only controls имеют accessible names;
- primary action не hover-only;
- dialogs/sheets управляют focus;
- keyboard не закрывает active field/submit;
- large text/long Russian strings не ломают controls;
- canvas/viewer DPR-aware, но resource-bounded;
- user zoom не блокируется.

Visual acceptance не заменяется Playwright. Playwright не заменяется screenshot review.

---

## 13. Пакетирование разработки

Hard ceiling из `MAINTAINABILITY.md` — не целевой размер.

Для следующих UI packages:

- предпочтительно **tiny/normal**;
- ориентир 5–15 touched files;
- один пользовательский outcome;
- один основной feature owner;
- соседний refactor запрещён без доказанной необходимости.

### Ближайший product package после gate/reconciliation

Scope:

- canonical docs reconciliation Chat-first facts;
- убрать manual `Инструменты` picker;
- `+` оставить honest attachment/context entry;
- исправить Help/navigation wording;
- targeted shell tests + representative screenshots.

Не входит:

- Chat backend;
- route migration Video/Audio/3D;
- `/chat/{threadId}`;
- Image editor;
- Video/Audio/3D runtime;
- Feed backend;
- backend financial/security semantics.

### Fail-first acceptance

Перед implementation должны существовать red cases:

1. Chat home не должен иметь постоянную кнопку `Инструменты`.
2. Help не должен инструктировать пользователя вручную выбирать tool внутри Chat.

После implementation дополнительно подтверждается:

- пять global creative workspaces остались доступны;
- `/studio/chat` current compatibility не сломана, если route migration не входит в package;
- Chat без backend не показывает assistant success;
- Image quote/submit/provider uncertainty regression suite green;
- shell responsive matrix green.

---

## 14. Canonical reconciliation — обязательная последовательность

Когда lifecycle разрешит новый package:

1. Обновить `PRODUCT.md`: Chat-first home, distinction Chat vs Studios, current/compatibility/pending routes.
2. Обновить `UX.md`: убрать устаревшее «первая страница/маршруты не утверждены» там, где решение уже принято; сохранить только visual/responsive ownership.
3. Перенести уникальные shell visual facts из `UX_PRODUCT_SHELL.md`; затем сократить/удалить его как duplicate owner.
4. В `ADMIN.md` явно разделить target A-registry и current implemented subset.
5. `ARCHITECTURE.md`/ADR менять только если реально вводится новый persistent entity/relationship.
6. Только после docs reconciliation менять UI source.

---

## 15. Definition of Done UX package

Package не завершён, пока нет одновременно:

- exact allowed scope;
- fail-first acceptance;
- TypeScript/build pass;
- targeted Playwright;
- профильных backend tests при semantic change;
- no-fake-runtime check;
- accessibility basics;
- responsive matrix;
- maintainability delta;
- exact-head required CI;
- independent review для high-risk;
- owner visual acceptance там, где меняется product shell/design.

Запрещено получать green путём расширения limits, удаления negative tests или превращения server truth в browser-local state.

---

## 16. Non-goals этого ТЗ

Это ТЗ не:

- объявляет все 75 registry surfaces реализованными;
- создаёт backend endpoints, которых нет;
- утверждает pending route/data-model decisions;
- обещает CAD/DAW/video editor раньше domain contracts;
- разрешает менять frozen FRONTEND-001;
- заменяет canonical PRODUCT/UX/ARCHITECTURE после reconciliation.

---

## 17. Handoff coding-agent

Для конкретной задачи агент получает только:

```text
Goal
Before -> After
Exact base/package
Allowed paths
Non-goals
Server invariants
Owner files
Nearest tests
Acceptance cases
Risk
```

Не передавать весь UX archive как default prompt.

Итоговое правило: **документация должна уменьшать стоимость следующей правки, а не становиться ещё одним продуктом, который нужно обслуживать.**