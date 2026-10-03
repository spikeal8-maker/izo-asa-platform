import { expect, test, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const A = { id: '11111111-1111-4111-8111-111111111131', title: 'Длинный разговор A', created_at: 1, updated_at: 2 }
const B = { id: '11111111-1111-4111-8111-111111111132', title: 'Разговор B', created_at: 1, updated_at: 2 }
const message = (sequence: number, thread = 'A') => ({
  id: `22222222-2222-4222-8222-${String(sequence + (thread === 'B' ? 200 : 0)).padStart(12, '0')}`,
  request_id: '33333333-3333-4333-8333-333333333333', role: 'user', sequence,
  content: `${thread} message ${sequence} ` + 'Длинный текст разговора. '.repeat(8),
  state: 'complete', attachments: [], created_at: 1, updated_at: 1,
})
const scroll = (page: Page) => page.locator('.chat-scroll')
const gate = () => {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  return { wait, release }
}
async function choose(page: Page, title: string) {
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) {
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  }
  await page.getByRole('button', { name: title }).click()
}

test.beforeEach(({}, info) => test.skip(!['phone-small', 'laptop'].includes(info.project.name)))

test('loads older messages once and keeps the reading position after prepend', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [A] } }))
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({ json: {
    thread: A, messages: Array.from({ length: 100 }, (_, i) => message(i + 21)), next_before_sequence: 21,
  } }))
  await page.route(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`, route => route.fulfill({ json: {
    messages: [...Array.from({ length: 20 }, (_, i) => message(i + 1)), message(21)], next_before_sequence: null,
  } }))
  await page.goto('/')
  await choose(page, A.title)
  await expect(page.getByText(/^A message 120 /)).toBeAttached()
  await choose(page, A.title)
  await expect(page.getByRole('button', { name: 'Загрузить ранние сообщения' })).toBeVisible()
  await scroll(page).evaluate(node => { node.scrollTop = 400 })
  const first = page.getByText(/^A message 21 /)
  const before = await first.boundingBox()
  await page.getByRole('button', { name: 'Загрузить ранние сообщения' })
    .evaluate(button => (button as HTMLButtonElement).click())
  await expect(page.getByText(/^A message 1 /)).toBeAttached()
  await expect(page.locator('.chat-turn')).toHaveCount(120)
  await expect(page.getByRole('button', { name: 'Загрузить ранние сообщения' })).toHaveCount(0)
  const after = await first.boundingBox()
  expect(Math.abs((after?.y ?? 0) - (before?.y ?? 0))).toBeLessThan(4)
  await page.reload()
  await choose(page, A.title)
  await expect(page.getByRole('button', { name: 'Загрузить ранние сообщения' })).toBeVisible()
  await expect(page.getByText(/^A message 1 /)).toHaveCount(0)
})

for (const fails of [false, true]) test(`late ${fails ? 'error' : 'page'} cannot contaminate another selected thread`, async ({ page }) => {
  await workspace(page)
  const delayed = gate()
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [A, B] } }))
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({ json: {
    thread: A, messages: Array.from({ length: 100 }, (_, i) => message(i + 21)), next_before_sequence: 21,
  } }))
  await page.route(`**/api/v1/chat/threads/${B.id}`, route => route.fulfill({ json: {
    thread: B, messages: [message(1, 'B')], next_before_sequence: null,
  } }))
  await page.route(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`, async route => {
    await delayed.wait
    if (fails) return route.fulfill({ status: 503, json: { error: { code: 'unavailable' } } })
    await route.fulfill({ json: { messages: [message(1)], next_before_sequence: null } })
  })
  await page.goto('/')
  await choose(page, A.title)
  const requested = page.waitForRequest(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения' }).click()
  await requested
  await choose(page, B.title)
  await expect(page.getByText(/^B message 1 /)).toBeAttached()
  delayed.release()
  await expect(page.getByText(/^A message 1 /)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Загрузить ранние сообщения' })).toHaveCount(0)
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('logout clears a pending older-page read', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/auth/logout', route => route.fulfill({ status: 204, body: '' }))
  const delayed = gate()
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [A] } }))
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({ json: {
    thread: A, messages: Array.from({ length: 100 }, (_, i) => message(i + 21)), next_before_sequence: 21,
  } }))
  await page.route(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`, async route => {
    await delayed.wait
    await route.fulfill({ json: { messages: [message(1)], next_before_sequence: null } })
  })
  await page.goto('/')
  await choose(page, A.title)
  const requested = page.waitForRequest(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения' }).click()
  await requested
  await page.getByRole('button', { name: 'Профиль', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Выйти' }).click()
  await expect(page.getByText(/^A message 120 /)).toHaveCount(0)
  delayed.release()
  await expect(page.getByText(/^A message 1 /)).toHaveCount(0)
})
