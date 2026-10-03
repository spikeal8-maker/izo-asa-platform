import { expect, test, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const threads = [
  { id: '11111111-1111-4111-8111-111111111131', title: 'Длинный разговор A', created_at: 1, updated_at: 2 },
  { id: '11111111-1111-4111-8111-111111111132', title: 'Длинный разговор B', created_at: 1, updated_at: 2 },
]
const [A, B] = threads
const messages = (label: string) => Array.from({ length: 25 }, (_, index) => ({
  id: `22222222-2222-4222-8222-${String(index + (label === 'A' ? 0 : 100)).padStart(12, '0')}`,
  role: 'user', sequence: index + 1, content: `${label} ${index} ` + 'Длинная строка разговора. '.repeat(12),
  state: 'complete', created_at: 1, updated_at: 1,
}))
const partial = (requestId: string, suffix: string) => ({
  id: `22222222-2222-4222-8222-2222222222${suffix}`, request_id: requestId,
  role: 'assistant', sequence: 26, content: '', state: 'partial', created_at: 1, updated_at: 1,
})
const gate = () => {
  let release!: () => void
  const wait = new Promise<void>(r => { release = r })
  return { wait, release }
}
test.beforeEach(({}, info) => test.skip(!['phone-small', 'laptop'].includes(info.project.name)))
const setup = async (page: Page, items = threads) => {
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: items } }))
}

async function choose(page: Page, title: string) {
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) {
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  }
  await page.getByRole('button', { name: title }).click()
}

for (const mode of ['early', 'late', 'failed'] as const) test(`stale A status: ${mode} return`, async ({ page }) => {
  await setup(page)
  const requestId = '33333333-3333-4333-8333-333333333334'
  const assistant = partial(requestId, '98')
  const delayedStatus = gate()
  const delayedB = gate()
  const admitted: string[] = []
  let streamed = 0
  let statusCalls = 0
  await page.route('**/api/v1/chat/threads/*', async route => {
    const isB = route.request().url().endsWith(B.id)
    if (isB) {
      await delayedB.wait
      if (mode === 'failed') return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    }
    const thread = isB ? B : A
    return route.fulfill({ json: { thread, messages: isB ? messages('B') : [...messages('A'), assistant] } })
  })
  await page.route(`**/api/v1/chat/requests/${requestId}`, async route => {
    statusCalls += 1
    await delayedStatus.wait
    return route.fulfill({ json: { id: requestId, thread_id: A.id, state: 'streaming' } })
  })
  await page.route(`**/api/v1/chat/requests/${requestId}/events`, route => {
    streamed += 1
    return route.abort()
  })
  await page.route('**/api/v1/chat/threads/*/requests', route => {
    admitted.push(new URL(route.request().url()).pathname)
    return route.fulfill({ json: { id: route.request().postDataJSON().request_id, state: 'pending' } })
  })
  await page.goto('/')
  const requested = page.waitForRequest(`**/api/v1/chat/requests/${requestId}`)
  await choose(page, A.title)
  await requested
  const statusSettled = Promise.race([
    page.waitForEvent('requestfinished', request => request.url().endsWith(`/api/v1/chat/requests/${requestId}`)),
    page.waitForEvent('requestfailed', request => request.url().endsWith(`/api/v1/chat/requests/${requestId}`)),
  ])
  await choose(page, B.title)
  if (mode === 'early') {
    await choose(page, A.title)
    await expect.poll(() => statusCalls).toBe(2)
  }
  if (mode === 'failed') {
    delayedB.release()
    await expect(page.getByRole('alert')).toBeVisible()
    delayedStatus.release()
    await expect.poll(() => streamed).toBe(1)
    return
  }
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  delayedStatus.release()
  await statusSettled
  await page.evaluate(() => new Promise<number>(requestAnimationFrame))
  if (mode === 'late') expect(streamed).toBe(0)
  delayedB.release()
  if (mode === 'early') {
    await expect.poll(() => streamed).toBe(1)
    await expect(page.getByText(/^B 24 /)).toHaveCount(0)
    return
  }
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  await expect(page.getByText(/^A 24 /)).toHaveCount(0)
  await expect(page.getByRole('alert')).toHaveCount(0)
  const draft = page.getByRole('textbox', { name: 'Сообщение' })
  await expect(draft).toBeEnabled()
  await expect(page.locator('[aria-label="Новый чат"]')).toBeEnabled()
  await expect(page.locator('.chat-history-item').first()).toBeEnabled()
  expect(streamed).toBe(0)
  await draft.fill('Ответить в B')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect.poll(() => admitted).toEqual([`/api/v1/chat/threads/${B.id}/requests`])
  await expect(draft).toBeEnabled()
  await choose(page, A.title)
  await expect.poll(() => streamed).toBe(1)
})

test('superseded B warning and failed C cannot carry A draft into B', async ({ page }) => {
  const C = { ...B, id: '11111111-1111-4111-8111-111111111133', title: 'Разговор C' }
  const requestId = '33333333-3333-4333-8333-333333333335'
  const warning = { ...partial(requestId, '97'), state: 'interrupted' }
  const warningGate = gate()
  const admitted: string[] = []
  await setup(page, [A, B, C])
  await page.route('**/api/v1/chat/threads/*', route => {
    const id = route.request().url()
    if (id.endsWith(C.id)) return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    const thread = id.endsWith(B.id) ? B : A
    return route.fulfill({ json: { thread, messages: [...messages(thread === B ? 'B' : 'A'),
      ...(thread === B ? [warning] : [])] } })
  })
  await page.route(`**/api/v1/chat/requests/${requestId}`, async route => {
    await warningGate.wait
    return route.fulfill({ json: { id: requestId, thread_id: B.id, state: 'stopped' } })
  })
  await page.route('**/api/v1/chat/threads/*/requests', route => {
    admitted.push(new URL(route.request().url()).pathname)
    return route.fulfill({ json: { id: route.request().postDataJSON().request_id, state: 'pending' } })
  })
  await page.goto('/')
  await choose(page, A.title)
  const draft = page.getByRole('textbox', { name: 'Сообщение' })
  await draft.fill('Черновик A')
  const warningRequested = page.waitForRequest(`**/api/v1/chat/requests/${requestId}`)
  await choose(page, B.title)
  await warningRequested
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  await choose(page, C.title)
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(draft).toBeEnabled()
  await expect(draft).toHaveValue('')
  await draft.fill('Сообщение B')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect.poll(() => admitted).toEqual([`/api/v1/chat/threads/${B.id}/requests`])
  warningGate.release()
})
