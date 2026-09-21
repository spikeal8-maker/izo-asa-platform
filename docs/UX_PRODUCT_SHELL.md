# IZO ASA · Product Shell + Semantic Color System v1.1

Статус: обязательный продуктовый и инженерный контракт текущего frontend shell.
Решение владельца заменяет прежний feed-first shell UX-002 там, где они расходятся. Главная поверхность продукта — Chat;
Feed остаётся отдельным публичным разделом Лента/Explore.
Обычная регистрация открытая. Guest image trial остаётся отдельным pre-auth flow и не меняет chat-first shell.

## 1. Канонический shell

- `/` — **Чат**. `/studio/chat` сохраняется как compatibility alias.
- Creative destinations: **Чат → Изображение → Видео → Звук → 3D**.
- Utility destinations: Лента, Галерея, Help, token indicators и Account.
- Один и тот же global header используется на Chat, Feed, Gallery, Account и остальных пользовательских surfaces.
- Global header всегда остаётся видимым при document scroll: desktop/mobile shell не создают отдельные несовместимые headers.
- Chat sidebar существует только на Chat и не является global application sidebar.
- Недоступный runtime нельзя изображать успешным. Пока server text-chat отсутствует, frontend не генерирует fake assistant answer.

## 2. Brand

Canonical logo asset:

```text
apps/web/public/favicon.svg
source:
spikeal8-maker/IZO_ASA/frontend/public/favicon.svg
```

Правила:
- logo asset не перерисовывается вручную внутри shell;
- `ИЗО` использует semantic warning token;
- `АСА` использует semantic brand token;
- название остаётся визуально заметным, но не должно подавлять product navigation;
- component CSS не создаёт новые brand HEX;
- favicon подключён и как browser favicon, и как header brand asset.

## 3. Header geometry

### Desktop

Base geometry около 1440px:
- header начинается с `x=0`;
- базовая высота — около `52px`;
- слева: Brand + Лента + Галерея;
- центр: Chat / Image / Video / Audio / 3D;
- справа: daily tokens + global tokens + Login/Avatar.

Desktop shell использует fluid scale через CSS `clamp()`, а не отдельные 2K/4K/8K дизайны.

Обязательное правило:
- изменение ширины окна не должно создавать horizontal overflow;
- controls не должны пересекаться;
- font/icon/control scale продолжает расти на 2K/4K/8K;
- reading/chat width остаётся bounded и не растягивается на всю панель.

### Mobile

Structural breakpoint: `<=760px`.

Header имеет две строки:
1. Brand + Лента/Галерея + два token indicators + Login/Avatar.
2. Chat / Изо / Видео / Звук / 3D.

Base mobile header: около `64px`.

Minimum supported CSS viewport: **320px**.

Для 320px разрешается более плотная геометрия controls, но обязательны:
- brand остаётся доступным;
- Лента и Галерея остаются различимыми;
- оба token indicators видимы;
- auth control видим;
- пять creative destinations видимы;
- document horizontal overflow отсутствует;
- header controls физически не пересекаются.

## 4. Fluid responsive scale

Desktop shell использует единый fluid диапазон.

Основные параметры:
- global header: `clamp(52px, ..., 96px)`;
- sidebar: `clamp(280px, 15vw, 640px)`;
- chat reading measure: `clamp(960px, 55vw, 2400px)`;
- composer measure: `clamp(900px, 50vw, 2200px)`;
- heading / product text / icons / tokens масштабируются через `clamp()`.

Нельзя снова вводить ступенчатую схему вида:

```text
1440 → size A
2200 → size B
3200 → size C
>3200 → size C forever
```

4K/8K должны получать физически более крупный UI, но reading measure остаётся ограниченным.

## 5. Chat layout

Desktop:
- sidebar начинается сразу под global header;
- sidebar attachment: `x=0`;
- sidebar не имеет outer content padding;
- main занимает всё освободившееся пространство при collapse;
- open-panel control появляется после collapse.

Mobile:
- sidebar стартует закрытой;
- открывается drawer-ом поверх main;
- отправка сообщения и выбор чата закрывают drawer;
- composer остаётся основным bottom interaction surface.

### Empty state

Empty Chat — единый layout block:

```text
chat-start-state
├── Чем я могу помочь?
└── composer
```

Heading и composer нельзя позиционировать двумя независимыми абсолютными формулами.

## 6. Keyboard / VisualViewport

Chat использует `window.visualViewport`.

При появлении экранной клавиатуры:
- global header остаётся внутри visible viewport;
- chat shell принимает реальную visual viewport height;
- composer поднимается над клавиатурой;
- safe-area учитывается;
- document не должен получать второй независимый vertical scroll.

Обязательная physical-device проверка перед release:
- Chrome Android;
- Safari iPhone;
- portrait/landscape;
- keyboard open/close;
- browser chrome resize.

Playwright viewport-shrink является regression gate, но не заменяет physical mobile acceptance.

## 7. Chat sidebar

Sidebar содержит:
- История;
- Новый чат;
- search icon;
- `Чаты`;
- реальную локальную историю текущей frontend session;
- authenticated profile block внизу.

Search:
- search input заменяет title `История`;
- Escape закрывает search;
- список фильтруется только по реально созданным chat entries;
- fake chat history запрещена.

Authenticated bottom profile и top avatar используют один `AccountMenu`:
- Аккаунт;
- Токены;
- Настройки;
- Помощь;
- Тема;
- social controls;
- Выйти.

VK/Instagram остаются disabled, пока в конфигурации нет достоверного canonical URL.
Telegram/MAX могут быть active только с проверенным URL.

## 8. Composer

Composer содержит:
- plus/tools;
- model selector;
- selected tool state;
- attachment state;
- microphone;
- send.

Tools menu:
- Добавить файл;
- Создать изображение;
- Создать видео;
- Создать звук;
- Создать 3D;
- Поиск в интернете.

File action использует настоящий browser file chooser.

Popovers:
- закрываются click-outside;
- Escape закрывает popup;
- focus возвращается к opener;
- ArrowUp / ArrowDown / Home / End поддерживают keyboard navigation по menu items.

## 9. Model selector

Default label:

```text
Авто
```

Категории:
- Текст;
- Изображения;
- Видео;
- Звук;
- 3D.

Frontend **не классифицирует модели по substring heuristics**.

Текущая временная граница:
- `apps/web/src/shell/chat/modelCatalog.ts` содержит explicit mapping только известных production capability IDs;
- неизвестные capability IDs не угадываются и не публикуются в selector;
- окончательная модель данных должна прийти из backend catalog с явными полями `id / display_name / category / availability`.

Пустая категория честно показывает отсутствие опубликованных моделей.

## 10. Voice capture

Microphone path:
- `navigator.mediaDevices.getUserMedia`;
- `AudioContext`;
- `AnalyserNode`;
- amplitude waveform.

Waveform:
- 48 bars;
- amplitude меняет bar scale;
- animation обновляет DOM bars через refs;
- весь Chat не должен React-render-иться 20–30 раз/секунд только из-за waveform;
- stop освобождает tracks и AudioContext;
- ended media track завершает voice mode.

Пока speech-to-text не подключён, UI не должен создавать fake transcript.

## 11. Component boundaries

Chat не должен снова превращаться в монолит.

Текущие границы:

```text
ChatPage
├── ChatSidebar
├── ChatComposer
│   ├── model catalog
│   └── voice capture
└── useVisualViewport
```

Files:

```text
apps/web/src/shell/ChatPage.tsx
apps/web/src/shell/chat/ChatSidebar.tsx
apps/web/src/shell/chat/ChatSidebar.css
apps/web/src/shell/chat/ChatComposer.tsx
apps/web/src/shell/chat/ChatComposer.css
apps/web/src/shell/chat/modelCatalog.ts
apps/web/src/shell/chat/useVoiceCapture.ts
apps/web/src/shell/chat/useVisualViewport.ts
apps/web/src/shell/chat.css
```

Правило: новая крупная capability не добавляется обратно непосредственно в `ChatPage.tsx`.

## 12. Semantic Color System v1.1

`apps/web/src/shell/theme.css` — runtime source of truth.

### Light

```css
--color-bg: #F6F6F8;
--color-surface: #FFFFFF;
--color-border: #D7DAE0;
--color-text: #181A1F;
--color-text-secondary: #4F5660;
--color-brand: #6E45C1;
--color-brand-soft: #F0ECF7;
--color-on-brand: #FFFFFF;
--color-success: #176B4A;
--color-warning: #8A5A00;
--color-error: #B73748;
```

### Dark

```css
--color-bg: #111318;
--color-surface: #191C22;
--color-border: #343A45;
--color-text: #F3F4F6;
--color-text-secondary: #B0B6C0;
--color-brand: #9D78EA;
--color-brand-soft: #2B2437;
--color-on-brand: #111318;
--color-success: #53C89A;
--color-warning: #F2B84D;
--color-error: #FF7A88;
```

Rules:
- neutral interface + один фирменный violet;
- новые component HEX запрещены;
- hover/focus/selected выводятся через semantic tokens и `color-mix`;
- generated content не ограничивается UI palette.

## 13. Token contract

Header содержит два отдельных indicators:
1. daily / sun;
2. global credits / gem.

Если daily backend source отсутствует:

```text
0/0
```

Global token value использует real `credits.balance.available`.

Frontend не создаёт fake positive balances и не изображает daily quota, которого backend не публикует.

Mobile geometry обязана выдерживать минимум трёхзначный balance без collision.

## 14. Responsive acceptance matrix

Обязательные viewport checks:

```text
320×568
360×740
390×844
430×932
768×1024
800×600
960×540
1024×768
1280×720
1366×768
1440×900
1600×900
1920×600
1920×1080
2560×1440
3440×1440
3840×2160
7680×4320
```

Также:
- DPR 1.5 / 2;
- Windows scaling 125 / 150 / 200%;
- browser window narrowing around structural breakpoint.

Acceptance:
- no document horizontal overflow;
- no visible control collision;
- global header remains visible while long pages scroll;
- 320px minimum passes;
- large-screen typography and controls continue scaling;
- Chat reading/composer remains bounded;
- mobile sidebar starts collapsed;
- keyboard keeps composer visible.

## 15. Frontend gates

Focused shell quality gate:
- `npm run typecheck`;
- `npm run build`;
- `e2e/shell.spec.ts`;
- `git diff --check`.

Backend suites не являются частью visual shell iteration, если backend contract не менялся.
