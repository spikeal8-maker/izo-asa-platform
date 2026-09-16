# IZO ASA UX v4 — open decisions

Статус: **staging decision queue**. Здесь только решения, которые нельзя безопасно вывести из текущего кода или уже подтверждённого Chat-first направления. Документ не меняет canonical product contract.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## Уже не открытые решения

Следующее в рамках v4 считается установленным owner/current direction и не должно снова обсуждаться каждым coding-agent:

- `/` — Chat-first product home в текущем frontend;
- top-level creative workspaces: Chat / Image / Video / Audio / 3D;
- Chat — intent-driven, direct parameter control остаётся в Studios;
- постоянный ручной `Инструменты` picker в Chat не входит в target;
- Gallery = private Assets, Jobs = operational execution history, Feed = separate public Publication surface;
- Semantic Color System v1.1 = neutral UI + one violet brand accent;
- mobile = адаптация тех же существенных действий, а не сжатый desktop;
- unsupported runtime не изображается работающим.

## O-01 — canonical routes Video / Audio / 3D

**Current:** `/studio/video`, `/studio/audio`, `/studio/3d` ведут в generic placeholder `SectionPage`.

**v4 candidate:** `/video`, `/audio`, `/3d` как canonical routes; `/studio/*` как compatibility aliases.

**Что требуется решить:** принять concise routes или сохранить `/studio/*` как постоянные canonical paths.

**Safe default до решения:** не создавать новые redirect/links; сохранить текущие рабочие paths и пометку placeholder.

## O-02 — durable Chat route model

**Current:** `/` и `/studio/chat` открывают локальную Chat surface без server threads/messages.

**Repo target:** PRODUCT/ARCHITECTURE предусматривают Chat threads/messages и исторические `/chat`, `/chat/{threadId}`.

**Что требуется решить после CHAT backend:**

- `/` = active/new conversation + `/chat/{threadId}` deep link; или
- `/chat/{threadId}` плюс отдельная `/chat` listing page; или
- история только sidebar/drawer при сохранении deep-linkable thread URL.

**Safe default:** до CHAT-001 не вводить route, который создаёт иллюзию durable thread persistence.

## O-03 — Image editor route

**Repo target:** исторический U-11 `/paint`.

**v4 UX:** editing является частью Image product, но точный route не подтверждён.

Возможные формы:

- integrated mode внутри `/image`;
- nested `/image/{assetId}/edit`;
- отдельный `/paint` как canonical или compatibility path.

**Safe default:** capability остаётся в target documentation; route не реализуется до IMAGE-002 contract.

## O-04 — VideoProject persistence

**v4 proposal:** timeline/project editing только если существует durable `VideoProject` с save/reopen/version semantics.

**Decision:** нужен ли продукту persistent project/timeline в первом Video editor release или достаточно generation + result/history.

**Safe default:** VIDEO-001 может реализовать generation workspace без fake project/timeline state.

## O-05 — AudioProject / multitrack scope

**v4 proposal:** waveform-first core; multitrack/automation = later project level.

**Decision:** вводить ли persistent AudioProject вообще и в каком package.

**Safe default:** TTS/ASR/upload/record/playback/simple processing могут существовать без DAW semantics.

## O-06 — 3D editor depth

**v4 levels:** A = generator/viewer; B = scene/material editing; C = full modeling/CAD-like work.

**Decision:** является ли Level B продуктовым требованием после generator/viewer и есть ли намерение идти к Level C.

**Safe default:** THREE-D-001 ограничивается real generator/manifest/viewer/download contract. Полное моделирование не подразумевается.

## O-07 — marketing/public landing after Chat-first `/`

Исторический PRODUCT U-01 предполагал отдельную общую главную на `/`. Current owner direction отдала `/` Chat.

**Decision:** требуется ли отдельная marketing/public landing surface вообще; если да — какой route и нужен ли он до launch.

**Safe default:** не возвращать Feed-first или marketing-first `/`; public Feed остаётся `/feed`, guest Chat shell может содержать минимальное product explanation.

## O-08 — lineage/version persistence beyond current Job → Asset

ARCHITECTURE уже имеет Asset/source links и Publication target, но UX v4 предлагает более явную lineage/version presentation.

**Decision:** достаточно ли текущих source links для derived assets или нужен отдельный version graph/document relation.

**Safe default:** UI показывает только lineage, реально подтверждённую API. Не создавать client-only version tree.

## Правило закрытия решения

Решение считается закрытым только когда:

1. owner/product decision сформулирован однозначно;
2. repository-owned `PRODUCT.md`/`UX.md`/`ARCHITECTURE.md`/ADR обновлены в разрешённом package;
3. route/data ownership и tests определены;
4. `OPEN_DECISIONS.md` staging-copy обновляется или помечается superseded;
5. код меняется после документа, а не вместо документа.

## Self-review

PASS:

- вопросы, уже установленные Chat-first направлением, не оставлены открытыми;
- unresolved route/entity choices не выданы за утверждённые;
- у каждого открытого решения есть fail-safe behavior;
- документ не требует backend сущности ради визуального макета;
- canonical branch/package state не изменён.
