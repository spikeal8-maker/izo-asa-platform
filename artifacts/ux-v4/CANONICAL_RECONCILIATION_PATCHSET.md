# IZO ASA UX v4 — canonical reconciliation patchset

Статус: **staging / ready-to-apply proposal**. Это не новый roadmap и не замена canonical docs. Применять только в новом package после штатного lifecycle gate.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. Цель следующего документационного прохода

Привести repository-owned контракты к фактически принятому Chat-first направлению без изменения backend semantics и без создания второго источника истины.

Главное правило: сначала согласовать route/ownership semantics в `PRODUCT.md` + `UX.md`/`UX_PRODUCT_SHELL.md`, затем менять router/components. Не наоборот.

## 2. PRODUCT.md — изменения, которые нужно подготовить

### 2.1. `/` и Chat

Текущее противоречие: U-01 описывает `/` как общую главную/marketing surface, а FRONTEND-001 уже делает `/` Chat home.

Предлагаемая нормализация:

- `/` = canonical Chat entry;
- `/studio/chat` = compatibility alias;
- public discovery остаётся `/feed`;
- marketing copy может существовать внутри guest Chat shell или отдельной public surface только после отдельного решения, но не должна возвращать Feed-first `/` автоматически.

### 2.2. `/app`

U-09 `/app` не имеет текущего router owner и создаёт второй creative hub. UX v4 не требует отдельный hub.

Предложение: перевести `/app` в legacy/redirect candidate на `/` после явного принятия route map. Не реализовывать отдельный dashboard только ради старой строки реестра.

### 2.3. Chat threads

Исторические U-15 `/chat` и U-16 `/chat/{threadId}` нужно разделить по смыслу:

- `/` — новый/текущий разговор;
- `/chat/{threadId}` — допустимый deep link после появления durable ChatThread backend;
- отдельная `/chat` listing page не обязательна, если история живёт в sidebar/drawer;
- до CHAT-001 никакие thread routes не должны имитировать server persistence.

### 2.4. Creative studio routes

Согласовать concise canonical routes:

- `/image`;
- `/video`;
- `/audio`;
- `/3d`.

`/studio/image`, `/studio/video`, `/studio/audio`, `/studio/3d`, `/studio/chat` после миграции остаются только aliases/redirects. Новые ссылки компонентов должны использовать concise routes.

### 2.5. Image editor

`/paint` остаётся unresolved decision. До решения нельзя удалять capability requirement из PRODUCT и нельзя создавать фиктивный editor route. Возможные варианты для отдельного owner decision: integrated `/image` mode, nested asset editor route или сохранение `/paint` alias.

## 3. UX_PRODUCT_SHELL.md — обязательная корректировка Chat semantics

Текущая строка «обычный диалог + запуск Image/Video/Audio/3D из одного composer» двусмысленно закрепляет ручной выбор инструментов и уже привела к visible `Инструменты` picker.

Целевой текст должен фиксировать:

- Chat = intent-driven conversational surface;
- пользователь пишет обычный запрос;
- internal agent/orchestrator сам выбирает разрешённую capability;
- internal model/provider/tool routing не показывается как постоянное меню;
- composer содержит message input, `+` для attachment/context, microphone и send;
- direct Image/Video/Audio/3D control остаётся в top-level Studios;
- Chat может показать typed result/job blocks и handoff «Открыть в студии» после появления runtime;
- до CHAT-001 frontend не показывает fake assistant/tool success.

Acceptance дополнить проверкой: на Chat home отсутствует постоянная кнопка/панель `Инструменты` для выбора Image/Video/Audio/3D.

## 4. UX.md — убрать устаревшую неопределённость там, где решение уже принято

Сейчас UX.md говорит, что точные маршруты и первая страница после входа ещё не утверждены. После owner Chat-first решения это слишком широкое утверждение.

Новая формулировка должна разделять:

- confirmed current: `/` Chat, `/image`, `/feed`, `/gallery`;
- compatibility current: `/studio/chat`, `/studio/image`;
- route decisions pending: concise Video/Audio/3D migration, ChatThread deep links, Image editor route;
- phone adaptation остаётся трансформацией той же бизнес-логики, а не отдельным продуктом.

## 5. ADMIN.md — разделить registry target и current implementation

A-01…A-30 остаются target registry. Добавить короткую implementation note:

- текущий frontend реально имеет user search/detail, audit и access delegation surfaces;
- credits доступны в рамках существующего user/admin contract;
- остальные `/admin/*` не считаются реализованными только потому, что `App.tsx` передаёт их в `AdminPage`;
- `AdminPage` сам fail-honest показывает «экран ещё не реализован» для неизвестного admin route.

Это предотвращает ложный вывод coding-agent, что весь A-01…A-30 уже существует.

## 6. ARCHITECTURE.md / ADR — что пока НЕ надо добавлять

Не создавать persistent сущности только ради UX-макета.

Отдельный ADR нужен только если соответствующий product package действительно вводит:

- `ChatThread` / durable messages;
- `VideoProject` / timeline persistence;
- `AudioProject` / multitrack persistence;
- editable Image/3D document version graph;
- shared lineage/version relation, выходящую за существующие Job → Asset → Publication semantics.

До этого Session UI/history не выдаётся за Project/Document domain object.

## 7. После принятия docs: минимальные frontend deltas

### ChatPage.tsx

- убрать `tools` array как постоянный ручной workspace picker;
- убрать `Инструменты` button и `chat-tools-popover`;
- `+` оставить owner attachment/context entry;
- не подключать fake tool execution;
- сохранить текущую честную runtime-note, пока CHAT-001 отсутствует.

### navigation.ts

- после route decision заменить новые Video/Audio/3D links на concise routes;
- обновить Chat description: не «запуск инструментов платформы» как ручной выбор, а intent-driven conversation;
- aliases принадлежат router, а не navigation source.

### SectionPage.tsx

- Help не должен инструктировать пользователя «выберите инструмент» внутри Chat;
- Video/Audio/3D placeholder cards допустимы только пока route/runtime явно помечены как недоступные; после появления настоящей Studio owner переносится из generic SectionPage в feature module.

### App.tsx/router

- aliases должны нормализоваться централизованно;
- unknown route продолжает fail-safe в 404;
- не добавлять новый mega-router branch для каждой будущей studio detail surface, если feature router/owner можно выделить отдельно.

## 8. Что нельзя ломать этим patchset

- текущий Image Entitlements/Credits/quote/operation-id/Job/Media chain;
- unknown paid outcome handling;
- Jobs polling/cancel/reconciliation semantics;
- private Gallery ownership;
- Auth/session/CSRF behavior;
- Admin permission checks;
- Semantic Color System v1.1;
- responsive viewport matrix и existing browser evidence expectations.

## 9. Тесты, которые должны сопровождать реализацию

1. `/` и `/studio/chat` дают одну Chat surface без `Инструменты` picker.
2. `+`, mic, send имеют однозначные accessible names; mic может быть disabled, если runtime нет.
3. Chat submit без backend не показывает assistant success.
4. canonical/alias route tests не создают loop и сохраняют deep-link behavior.
5. `/image` regression: quote → submit safety остаётся без изменений.
6. `/jobs` и `/jobs/{id}` продолжают различать active/reconciling/unknown/cancel states.
7. `/feed` presentation examples остаются явно не реальными публикациями до FEED-001.
8. unknown `/admin/*` не выглядит реализованным и не раскрывает privileged data.
9. mobile/desktop/QHD/UHD/HiDPI shell matrix остаётся green.

## 10. Package boundary

Этот patchset не должен применяться поверх frozen `FRONTEND-001`. Следующий package стартует только через штатный `project_state.py begin-next` после required evidence. Staging branch не является canonical lineage и не заменяет package transition.

## 11. Self-review

PASS как proposal:

- изменения разделены по canonical document owners;
- route conflicts не замаскированы под готовое решение;
- backend contract не переписывается UX-документом;
- future Project entities не выдумываются;
- implementation deltas ограничены тем, что следует из принятых UX decisions;
- ни один current paid/security invariant не предлагается ослабить.
