# IZO ASA UX v4 — minimal Chat patch preview

Status: **staging / exact-source preview**. This is not applied source code. It records the smallest implementation expected after the canonical docs are reconciled in a real package.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## 1. `apps/web/src/shell/ChatPage.tsx`

### Imports

Current:

```ts
import { Icon, type IconName } from '../shared/ui/Icon'
import { Link } from './router'
```

Target for the bounded package:

```ts
import { Icon } from '../shared/ui/Icon'
```

Reason: `IconName` and `Link` are only needed by the current manual workspace picker.

### Remove the manual tool catalog

Delete the current `tools` constant containing Image/Video/Audio/3D links.

Delete:

```ts
const [toolsOpen, setToolsOpen] = useState(false)
```

and delete the `setToolsOpen(false)` call from `submit()`.

### Composer left controls

Current behavior: both `+` and `Инструменты` toggle the same workspace popover.

Target interim behavior while Chat attachments/runtime do not exist:

```tsx
<div className="chat-composer-left">
  <button
    type="button"
    className="chat-circle-button"
    aria-label="Добавить"
    disabled
    title="Вложения в чат будут подключены вместе с серверным Chat runtime"
  >
    <Icon name="plus" />
  </button>
</div>
```

This keeps the target Chat geometry honest: `+` exists as the future attachment/context entry, but it does not pretend that upload/context handling works before the server contract exists.

Keep the existing disabled microphone and send behavior. Send still records the local user turn and shows the explicit unavailable-runtime notice; it must not render an assistant result.

### Remove popover markup

Delete the entire `chat-tools-popover` block and the separate `Инструменты` button.

No Image/Video/Audio/3D direct links are added inside the composer. Those workspaces remain reachable from global creative navigation.

## 2. `apps/web/src/shell/chat.css`

Delete only selectors that become dead after removing the manual picker:

- `.chat-tools-button`
- `.chat-tools-button:hover`
- `.chat-tools-button .icon`
- `.chat-tools-popover`
- `.chat-tool-item`
- `.chat-tool-item:hover`
- `.chat-tool-item > .icon`
- `.chat-tool-item span`
- `.chat-tool-item strong`
- `.chat-tool-item small`
- the mobile `.chat-tools-button` rule
- the mobile `.chat-tools-popover` rule

Do not change composer width, empty-state position, mobile dock/safe-area geometry, brand colors or other shell spacing in this bounded package unless the owner visual review finds a separate defect.

## 3. `apps/web/src/shell/navigation.ts`

Current Chat description:

```ts
'Главная поверхность: разговор и запуск инструментов платформы.'
```

Target wording:

```ts
'Главная поверхность: разговор на естественном языке; прямые инструменты доступны в отдельных студиях.'
```

This changes product semantics/copy only. Do not change workspace paths in this package.

## 4. `apps/web/src/shell/SectionPage.tsx`

Current Help Chat guidance:

```ts
'Начните с обычного запроса и выберите инструмент, если нужен результат другого типа.'
```

Target wording:

```ts
'Опишите задачу обычным языком. Прямые инструменты для изображений, видео, звука и 3D доступны отдельными разделами.'
```

Do not convert Video/Audio/3D placeholder cards into fake runtime surfaces.

## 5. `apps/web/e2e/shell.spec.ts`

Add the two fail-first cases from `FAIL_FIRST_ACCEPTANCE.md`:

1. Chat has no persistent button named `Инструменты`, while `Добавить`, `Голосовой ввод`, `Отправить` remain present.
2. `/help` contains no `выберите инструмент` wording.

Also retain/confirm the existing tests for five creative modes, `/studio/chat` compatibility, theme persistence, mobile navigation, 8K layout and platform hints.

## 6. Why `+` is disabled in this preview

The current Chat surface has no server attachment/context contract. Reusing `+` as a hidden workspace selector is the wrong product model; making it open a fake local source picker would be another false capability. A disabled but correctly named future attachment control is the smallest honest transition.

When `CHAT-001` or a dedicated attachment contract exists, `+` can open a real source sheet using server-owned Media/upload semantics. That future change requires its own acceptance cases.

## 7. Files explicitly not touched

- `App.tsx`
- `router.tsx`
- `TopBar.tsx`
- Image Studio files
- Gallery files
- Account/Auth files
- Admin files
- any backend source

## Self-review

PASS as an exact-source preview: the edit removes only obsolete manual-picker code/copy, deletes its dead CSS, preserves current Chat honesty and shell geometry, does not migrate routes, and does not touch working paid/security semantics.