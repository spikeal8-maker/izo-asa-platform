# IZO ASA UX v4 — decisions

Статус: **staging decision register / не canonical**.

Здесь только решения, которые действительно требуют owner choice. Всё остальное убрано из decision noise.

## A. Ближайшие решения — влияют на IA/routes

### D-01 — canonical routes Video / Audio / 3D

**Current:** `/studio/video`, `/studio/audio`, `/studio/3d` — placeholder surfaces.

**Рекомендация:**

```text
/video
/audio
/3d
```

с `/studio/*` как compatibility aliases после отдельной route migration.

**До решения:** не менять текущие рабочие paths.

**Canonical owners после принятия:** `PRODUCT.md`, затем router tests.

### D-02 — durable Chat URL model

**Current:** `/` + compatibility `/studio/chat`, без server threads.

**Рекомендация после появления ChatThread backend:**

```text
/                  new/current conversation
/chat/{threadId}   durable deep link
```

History — sidebar/drawer; отдельная `/chat` listing page не обязательна.

**До CHAT backend:** не создавать route, имитирующий persistence.

### D-03 — Image editor route

**Рекомендация:** `/image/{assetId}/edit`; `/image` остаётся create/generation studio; `/paint` только legacy alias при доказанной необходимости.

**Причина:** source Asset и ownership явно определены URL context; reload/deep-link однозначны.

**До IMAGE editor backend:** capability остаётся target-only.

---

## B. Отложенные scope/data-model decisions — не блокируют ближайший Chat package

### D-04 — VideoProject

**Default:** первый Video release = generation/result/history без persistent timeline project.

VideoProject вводить только вместе с save/reopen/revision semantics.

### D-05 — AudioProject / DAW

**Default:** первый Audio release = TTS/ASR/upload/record/playback/transcript и реально поддержанные simple operations.

Multitrack/automation требуют отдельного AudioProject contract.

### D-06 — 3D editor depth

**Default:** первый 3D release = generator + validated manifest + poster/viewer + export/download.

Scene/material editing — later. Full CAD не подразумевается.

### D-07 — separate marketing home

**Default:** отдельную marketing landing пока не вводить. `/` остаётся Chat-first; public discovery = `/feed`; guest shell может кратко объяснять продукт.

### D-08 — lineage/version graph

**Default:** показывать только реально сохранённые source/derived relations. Не создавать отдельный version graph до появления persistent editable-document semantics.

---

## C. Уже установленные решения — не переоткрывать в каждом package

- Product имеет пять top-level creative workspaces: Chat / Image / Video / Audio / 3D.
- Chat intent-driven; direct tools живут в Studios.
- Persistent manual `Инструменты` picker не входит в target Chat.
- Gallery = private Assets.
- Jobs = operational execution history.
- Feed = separate public Publication surface.
- Unsupported runtime не изображается работающим.
- Semantic Color System v1.1: neutral UI + one violet brand accent.
- Phone — transformed layout с теми же существенными действиями, не уменьшенный desktop.

## D. Правило принятия

Decision считается принятой только если:

1. owner choice сформулирован однозначно;
2. соответствующий canonical document обновлён в разрешённом package;
3. ownership/tests определены;
4. code change следует после документа.

Checkbox/issue/comment без canonical reconciliation сам по себе не меняет product contract.
