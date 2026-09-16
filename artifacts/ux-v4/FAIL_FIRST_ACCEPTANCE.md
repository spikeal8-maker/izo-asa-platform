# IZO ASA UX v4 — fail-first acceptance for Chat reconciliation

Status: **staging test contract**. These cases define the first expected red tests for the bounded Chat reconciliation package. They do not modify the frozen canonical branch.

Source snapshot: `ux/frontend-reset` @ `5c0e79b6fc3a7120207d0889b176fbfed3dab973`.

## A-01 — no persistent workspace picker in Chat

Current evidence: `ChatPage.tsx` renders a button with visible text `Инструменты` and a popover containing Image/Video/Audio/3D links.

Add to `apps/web/e2e/shell.spec.ts` before implementation:

```ts
test('chat composer does not expose a persistent workspace picker', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Инструменты' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Добавить' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Голосовой ввод' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Отправить' })).toBeVisible()
})
```

Expected on current head: **FAIL** because `Инструменты` exists.

## A-02 — top-level Studios remain reachable

Removing the Chat picker must not hide direct creative workspaces.

```ts
test('creative workspaces stay in global navigation', async ({ page }) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Творческие инструменты ИЗО АСА' })
  await expect(nav.getByRole('link')).toHaveCount(5)
  for (const name of ['Чат', 'Изображение', 'Видео', 'Звук', '3D']) {
    await expect(nav.getByRole('link', { name, exact: true })).toBeVisible()
  }
})
```

Expected on current head: **PASS**. This is a regression guard, not the failing trigger.

## A-03 — Chat remains honest without text runtime

```ts
test('chat without backend never fabricates assistant success', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Сделай изображение кота')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect(page.getByText(/помощник пока не подключён к серверу/i)).toBeVisible()
  await expect(page.locator('.chat-turn-user')).toHaveCount(1)
  await expect(page.locator('.chat-turn-assistant')).toHaveCount(0)
})
```

Expected on current head: **PASS**. Keep this behavior until `CHAT-001` supplies server truth.

## A-04 — Help must not teach manual Chat tool selection

Current `SectionPage.tsx` Help copy says: `Начните с обычного запроса и выберите инструмент, если нужен результат другого типа.`

```ts
test('help describes intent-driven Chat rather than manual tool selection', async ({ page }) => {
  await page.goto('/help')
  await expect(page.getByText(/выберите инструмент/i)).toHaveCount(0)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Помощь')
})
```

Expected on current head: **FAIL**.

## A-05 — compatibility alias remains identical

```ts
test('chat alias keeps the same product surface', async ({ page }) => {
  for (const path of ['/', '/studio/chat']) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Чем я могу помочь?')
    await expect(page.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
  }
})
```

Expected on current head: **PASS**. This package does not migrate aliases.

## A-06 — Image paid-safety regression guard

Do not rewrite Studio tests for the Chat change. The existing Image suite must still prove the quote -> stable-operation submit path, lost-response behavior and provider uncertainty. The bounded package should run `e2e/studio.spec.ts` and `e2e/provider.spec.ts` unchanged unless a shared shell change genuinely requires an assertion update.

## A-07 — docs regression guard

If `tests/test_docs_system.py` is changed, it should reject these stale assumptions after reconciliation:

- Chat is described as a permanent manual Image/Video/Audio/3D picker;
- first page after login is still globally "undecided" despite current Chat-first owner direction;
- placeholder Video/Audio/3D routes are documented as working generation runtime.

It must not hardcode mutable branch/SHA/PR into stable docs.

## A-08 — viewport evidence

The implementation must run the existing shell matrix, not only one desktop viewport. At minimum verify current configured phone/tablet/desktop/QHD/UHD/8K/HiDPI projects. Acceptance must include no document-level horizontal overflow and no overlap of the composer with mobile navigation/safe area.

## Test order

1. Add A-01 and A-04 and confirm they fail on the current implementation for the expected reasons.
2. Make the smallest Chat/copy change.
3. Run A-01..A-05.
4. Run current Studio/provider/Gallery/account/admin specs affected by shared shell.
5. Run docs/state/scope/headroom checks.
6. Run full required CI on the exact final source head.

## Self-review

PASS: two cases are intentionally red on the current head, remaining cases preserve known-good behavior, and no test requires a backend capability that does not exist.