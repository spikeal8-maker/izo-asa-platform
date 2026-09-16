# IZO ASA UX v4 — owner decision packet

Статус: **staging / recommendations, not canonical decisions**. Цель — свести оставшиеся product choices к коротким решениям с техническими последствиями.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## Рекомендуемый набор defaults

| ID | Рекомендация | Почему | Что это разблокирует |
|---|---|---|---|
| O-01 | canonical `/video`, `/audio`, `/3d`; `/studio/*` только compatibility aliases | короткие стабильные product routes, одинаковая схема с `/image` | единая top-level navigation и будущие real Studios |
| O-02 | `/` = new/current Chat; durable `/chat/{threadId}`; history в sidebar/drawer, без отдельной listing-page | сохраняет Chat-first и deep links без второго Chat продукта | CHAT-001 routing/persistence |
| O-03 | editor deep link `/image/{assetId}/edit`; `/image` остаётся create Studio; `/paint` только optional legacy alias | edit имеет конкретный owned source Asset и безопасный Back/deep-link | IMAGE-002 без смешения create/edit state |
| O-04 | VIDEO-001 сначала generation/result, без persistent timeline project | не вводить VideoProject до реальной потребности save/reopen/version | более ранний рабочий Video release |
| O-05 | AUDIO-001 сначала TTS/ASR/upload/record/playback/simple processing, без DAW project | multitrack резко расширяет data/runtime/UX scope | рабочий Audio core без fake DAW |
| O-06 | THREE-D-001 = generator + manifest + viewer + export/download; scene/material editing отдельным later package; full CAD не обещать | соответствует реальной backend границе и resource budget | честный 3D release без переоценки scope |
| O-07 | отдельный marketing landing пока не вводить; `/` остаётся Chat, guest shell объясняет продукт, public discovery = `/feed` | не возвращает второй competing home | сохраняет принятую Chat-first IA |
| O-08 | использовать существующие Asset source links как lineage v1; отдельный version graph вводить только вместе с persistent editor/document semantics | не создавать новую data model только ради UI | Gallery lineage без преждевременной migration |

## O-01 — routes Video / Audio / 3D

Рекомендованный target:

```text
/video
/audio
/3d
```

Compatibility:

```text
/studio/video -> /video
/studio/audio -> /audio
/studio/3d    -> /3d
/studio/chat  -> /
/studio/image -> /image
```

Redirect/alias должен принадлежать router layer. `navigation.ts` и feature components после migration используют только canonical routes.

Не выполнять эту migration в bounded Chat reconciliation package: current placeholder paths должны продолжить работать до отдельного route package.

## O-02 — Chat URL model

Рекомендованный target после CHAT-001:

```text
/                  new/current conversation
/chat/{threadId}   durable conversation deep link
```

History:

- desktop sidebar;
- phone drawer/sheet;
- search/new/rename/delete как controls этого history surface.

Отдельная `/chat` listing page не нужна, если history полностью доступна из Chat shell. `/chat` может быть compatibility redirect на `/` при необходимости.

## O-03 — Image editor

Рекомендованный target:

```text
/image                    create/generation studio
/image/{assetId}/edit     edit an owned asset/document context
```

Плюсы nested route:

- source ownership виден из URL context;
- deep link/reload имеют однозначный source asset;
- create Studio не хранит скрытый editor identity;
- Back/handoff из Gallery естественны.

`/paint` не использовать как новое canonical имя. Если старые ссылки реально нужны — только alias после ownership tests.

## O-04 — Video project

VIDEO-001 должен доказать прежде всего:

- text/image/reference input;
- quote/cost;
- Job lifecycle;
- player/result;
- save Asset;
- reuse/download/handoff.

Timeline/project вводить позже только с `VideoProject` persistence, revision/save/reopen contract. CSS timeline без persistent semantics запрещён.

## O-05 — Audio project

Первый Audio должен быть waveform/result oriented, но не multitrack DAW.

Core:

- upload/record;
- TTS;
- ASR;
- playback;
- transcript;
- basic trim/fade/gain/normalize/noise operations только если backend capability реально существует;
- export/save Asset.

`AudioProject` нужен только для настоящих multitrack/mix/automation semantics.

## O-06 — 3D depth

Первый contract:

```text
Text/Image -> Job -> 3D manifest -> poster -> on-demand viewer -> download/export
```

Resource fallback обязателен: слабое устройство может остаться на poster/download.

Scene/material editing — отдельный Level B. Full modeling/CAD — отдельное product decision; наличие viewer его не обещает.

## O-07 — public/marketing home

Рекомендация: не вводить отдельную marketing page до появления конкретной launch необходимости.

Guest `/` может содержать:

- одну короткую product explanation;
- Chat composer;
- login/register;
- переходы в Feed и доступные Studios.

Это сохраняет одну mental model вместо `/`, `/app`, `/chat` как трёх competing home surfaces.

## O-08 — lineage/versioning

V1 UI показывает только доказанные source relations:

```text
source Asset -> Job/operation -> result Asset -> Publication
```

Если IMAGE-002/VideoProject/AudioProject позже вводят сохранённые editable revisions, тогда отдельный ADR решает, нужен ли version graph/document root.

Не строить client-only дерево версий из timestamps/названий файлов.

## Рекомендуемый порядок принятия

O-01/O-02/O-03 — route decisions; должны попасть в PRODUCT/UX до соответствующих router changes.

O-04/O-05/O-06 — scope decisions для будущих modality packages; их можно принять как default сейчас, а точные runtime capabilities фиксировать позже.

O-07 — информационная архитектура launch.

O-08 — data-model restraint: принять как правило «не вводить graph до persistent editing semantics».

## Что эти рекомендации НЕ разрешают

- не разрешают менять frozen `FRONTEND-001`;
- не закрывают independent review;
- не чинят `project_state` deadlock;
- не создают Video/Audio/3D backend;
- не вводят new migrations/entities;
- не меняют canonical docs сами по себе.

## Self-review

PASS as recommendation packet:

- каждый default минимизирует premature persistence/schema complexity;
- direct Studios остаются first-class;
- Chat-first direction сохраняется;
- routes отделены от runtime scope;
- unresolved choices не выданы за уже принятые owner decisions.
