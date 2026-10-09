import { expect, test } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const thread = { id: '11111111-1111-4111-8111-111111111141', title: 'Copy test', created_at: 1, updated_at: 2 }
const assistant = '**Bold** [link](https://example.invalid)\n\n- [x] Done\n- [ ] Next\n\n| Name | Value |\n| --- | --- |\n| A | B |\n\n```js\nconst x = 1\n```'
const messages = [
  { id: '22222222-2222-4222-8222-222222222241', request_id: '33333333-3333-4333-8333-333333333341', role: 'user', sequence: 1, content: 'Hello **literal**', state: 'complete', attachments: [], created_at: 1, updated_at: 1 },
  { id: '22222222-2222-4222-8222-222222222242', request_id: '33333333-3333-4333-8333-333333333342', role: 'assistant', sequence: 2, content: assistant, state: 'complete', attachments: [], created_at: 2, updated_at: 2 },
]

test.beforeEach(({}, info) => test.skip(!['phone-small', 'laptop'].includes(info.project.name)))

test('copies saved user text, assistant plain text, and exact Markdown after reload', async ({ page }) => {
  await workspace(page)
  await page.addInitScript(() => {
    const copied: string[] = []
    Object.defineProperty(window, '__copied', { value: copied })
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text: string) => { copied.push(text) } }, configurable: true })
  })
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [thread] } }))
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: { thread, messages, next_before_sequence: null } }))
  await page.goto('/')
  async function openThread() {
    if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) await page.getByRole('button', { name: 'Открыть панель' }).click()
    await page.getByRole('button', { name: thread.title }).click()
  }
  await openThread()
  const user = page.locator(`[data-message-id="${messages[0].id}"]`)
  const answer = page.locator(`[data-message-id="${messages[1].id}"]`)
  await user.getByRole('button', { name: 'Копировать', exact: true }).click()
  await expect(user.getByRole('status')).toHaveText('Скопировано')
  await answer.locator('.chat-message-actions').getByRole('button', { name: 'Копировать', exact: true }).click()
  await answer.getByRole('button', { name: 'Копировать Markdown' }).click()
  expect(await page.evaluate(() => (window as any).__copied)).toEqual([
    'Hello **literal**',
    'Bold link\n\n- [x] Done\n- [ ] Next\n\nName\tValue\nA\tB\n\nconst x = 1',
    assistant,
  ])
  await page.reload()
  await openThread()
  await page.locator(`[data-message-id="${messages[1].id}"]`).getByRole('button', { name: 'Копировать Markdown' }).click()
  expect(await page.evaluate(() => (window as any).__copied)).toEqual([assistant])
})

test('clipboard rejection reports an error without claiming success', async ({ page }) => {
  await workspace(page)
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: async () => { throw new Error('denied') } }, configurable: true,
  }))
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [thread] } }))
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: { thread, messages, next_before_sequence: null } }))
  await page.goto('/')
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) await page.getByRole('button', { name: 'Открыть панель' }).click()
  await page.getByRole('button', { name: thread.title }).click()
  const answer = page.locator(`[data-message-id="${messages[1].id}"]`)
  await answer.getByRole('button', { name: 'Копировать Markdown' }).click()
  await expect(answer.getByRole('status')).toContainText('Не удалось скопировать')
})

test('copy uses current partial content and saved final content after reload', async ({ page }) => {
  await workspace(page)
  await page.addInitScript(() => {
    Object.defineProperty(window, '__copied', { value: [] })
    Object.defineProperty(navigator, 'clipboard', { value: {
      writeText: async (text: string) => { (window as any).__copied.push(text) },
    }, configurable: true })
  })
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [thread] } }))
  let current = { ...messages[1], content: '**Work', state: 'partial' }
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: {
    thread, messages: [current], next_before_sequence: null,
  } }))
  await page.goto('/')
  async function openThread() {
    if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) await page.getByRole('button', { name: 'Открыть панель' }).click()
    await page.getByRole('button', { name: thread.title }).click()
  }
  await openThread()
  await page.locator(`[data-message-id="${current.id}"]`).getByRole('button', { name: 'Копировать Markdown' }).click()
  expect(await page.evaluate(() => (window as any).__copied)).toEqual(['**Work'])
  current = { ...current, content: '**Work done**', state: 'complete' }
  await page.reload()
  await openThread()
  await page.locator(`[data-message-id="${current.id}"]`).getByRole('button', { name: 'Копировать Markdown' }).click()
  expect(await page.evaluate(() => (window as any).__copied)).toEqual(['**Work done**'])
})
