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

test('late image growth above the viewport keeps the same reading anchor', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [A] } }))
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({ json: {
    thread: A, messages: Array.from({ length: 100 }, (_, i) => message(i + 21)), next_before_sequence: 21,
  } }))
  const attachment = { id: '44444444-4444-4444-8444-444444444444',
    asset_id: '55555555-5555-4555-8555-555555555555', media_type: 'image/png',
    byte_size: 128, width: 220, height: 260, sha256: 'a'.repeat(64), created_at: 1 }
  await page.route(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`, route => route.fulfill({ json: {
    messages: [{ ...message(1), attachments: [attachment] }], next_before_sequence: null,
  } }))
  await page.goto('/')
  await choose(page, A.title)
  await expect(page.getByText(/^A message 120 /)).toBeAttached()
  await scroll(page).evaluate(node => {
    (node as HTMLElement).style.overflowAnchor = 'none'
    node.scrollTop = 400
  })
  const reader = page.getByText(/^A message 25 /)
  const before = await reader.boundingBox()
  await page.getByRole('button', { name: 'Загрузить ранние сообщения' })
    .evaluate(button => (button as HTMLButtonElement).click())
  const image = page.locator('.chat-message-image')
  await expect(image).toBeAttached()
  await expect.poll(async () => (await reader.boundingBox())?.y).toBeCloseTo(before!.y, 0)
  const composer = page.getByRole('textbox', { name: 'Сообщение' })
  await expect(composer).toBeEnabled()
  await composer.focus()
  await composer.press('Space')
  await image.evaluate(node => { (node as HTMLElement).style.height = '260px' })
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  await expect.poll(async () => Math.abs(((await reader.boundingBox())?.y ?? 0) - before!.y))
    .toBeLessThan(4)
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

test('a pending A page does not block loading older messages in B', async ({ page }) => {
  await workspace(page)
  const delayedA = gate()
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [A, B] } }))
  for (const thread of [A, B]) {
    await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: {
      thread, messages: Array.from({ length: 100 }, (_, i) => message(i + 21, thread === A ? 'A' : 'B')),
      next_before_sequence: 21,
    } }))
  }
  await page.route(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`, async route => {
    await delayedA.wait
    await route.fulfill({ json: { messages: [message(1)], next_before_sequence: null } })
  })
  await page.route(`**/api/v1/chat/threads/${B.id}/messages?before_sequence=21`, route => route.fulfill({ json: {
    messages: [message(1, 'B')], next_before_sequence: null,
  } }))
  await page.goto('/')
  await choose(page, A.title)
  const requestedA = page.waitForRequest(`**/api/v1/chat/threads/${A.id}/messages?before_sequence=21`)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения' }).click()
  await requestedA
  await choose(page, B.title)
  await expect(page.getByText(/^B message 120 /)).toBeAttached()
  await expect(page.getByRole('button', { name: 'Загрузить ранние сообщения' })).toBeEnabled()
  await page.getByRole('button', { name: 'Загрузить ранние сообщения' }).click()
  await expect(page.getByText(/^B message 1 /)).toBeAttached()
  delayedA.release()
  await expect(page.getByText(/^A message 1 /)).toHaveCount(0)
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

test('assistant prose uses primary theme text and has no visible role heading', async ({ page }) => {
  await workspace(page)
  const assistant = { ...message(1), role: 'assistant', content: 'Основной ответ ассистента' }
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [A] } }))
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({ json: {
    thread: A, messages: [assistant], next_before_sequence: null,
  } }))
  await page.goto('/')
  await choose(page, A.title)
  const prose = page.locator('.chat-assistant-message > p')
  await expect(prose).toHaveText('Основной ответ ассистента')
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, theme)
    const [proseColor, bodyColor] = await Promise.all([
      prose.evaluate(node => getComputedStyle(node).color),
      page.locator('body').evaluate(node => getComputedStyle(node).color),
    ])
    expect(proseColor).toBe(bodyColor)
  }
  await expect(page.getByText(/^(Ответ бота|Ответ ассистента|Assistant|AI response)$/)).toHaveCount(0)
})
