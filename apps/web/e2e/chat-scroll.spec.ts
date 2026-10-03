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
const scroll = (page: Page) => page.locator('.chat-scroll')
const distanceFromBottom = (page: Page) => scroll(page).evaluate(node =>
  node.scrollHeight - node.clientHeight - node.scrollTop)
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

test('delayed history load and A→B→A restore the reader viewport', async ({ page }) => {
  await setup(page)
  const delayedB = gate()
  await page.route('**/api/v1/chat/threads/*', async route => {
    const thread = threads.find(item => route.request().url().endsWith(item.id))!
    if (thread === B) await delayedB.wait
    await route.fulfill({ json: { thread, messages: messages(thread === A ? 'A' : 'B') } })
  })
  await page.goto('/')
  await choose(page, A.title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await scroll(page).evaluate(node => { node.scrollTop = 220 })
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(200)
  await choose(page, B.title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  expect(await scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(200)
  delayedB.release()
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await choose(page, A.title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(200)
  expect(await scroll(page).evaluate(node => node.scrollTop)).toBeLessThanOrEqual(240)
})

for (const staleFails of [false, true]) test(`latest selected thread ignores late ${staleFails ? 'error' : 'response'}`, async ({ page }) => {
  await setup(page)
  const delayedA = gate()
  await page.route('**/api/v1/chat/threads/*', async route => {
    const isA = route.request().url().endsWith(A.id)
    if (isA) {
      await delayedA.wait
      if (staleFails) return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    }
    const thread = isA ? A : B
    return route.fulfill({ json: { thread, messages: messages(isA ? 'A' : 'B') } })
  })
  await page.goto('/')
  const requestedA = page.waitForRequest(`**/api/v1/chat/threads/${A.id}`)
  await choose(page, A.title)
  await requestedA
  await choose(page, B.title)
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  const staleSettled = page.waitForEvent('requestfinished', request => request.url().endsWith(A.id))
  delayedA.release()
  await staleSettled
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  await expect(page.getByText(/^A 24 /)).toHaveCount(0)
  await expect(page.locator('.chat-history-item.active')).toHaveText(B.title)
  await expect(page.getByRole('alert')).toHaveCount(0)
})

for (const fails of [false, true]) test(`opening a thread ${fails ? 'fails safely' : 'cannot send to the old thread'}`, async ({ page }) => {
  await setup(page)
  const admitted: string[] = []
  const delayedB = gate()
  await page.route('**/api/v1/chat/threads/*', async route => {
    const isB = route.request().url().endsWith(B.id)
    if (isB) await delayedB.wait
    if (isB && fails) return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    const thread = isB ? B : A
    return route.fulfill({ json: { thread, messages: messages(isB ? 'B' : 'A') } })
  })
  await page.route('**/api/v1/chat/threads/*/requests', route => {
    admitted.push(new URL(route.request().url()).pathname)
    return route.fulfill({ json: { id: route.request().postDataJSON().request_id, state: 'pending' } })
  })
  await page.route('**/api/v1/chat/requests/*/events', route => route.fulfill({
    headers: { 'content-type': 'text/event-stream' }, body: 'event: message.completed\ndata: {}\n\n',
  }))
  await page.goto('/')
  await choose(page, A.title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  const draft = page.getByRole('textbox', { name: 'Сообщение' })
  await draft.fill('Проверить адресата')
  await choose(page, B.title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect(draft).toBeDisabled()
  await page.locator('.chat-composer').evaluate(form => (form as HTMLFormElement).requestSubmit())
  expect(await draft.inputValue()).toBe('Проверить адресата')
  expect(admitted).toEqual([])
  delayedB.release()
  if (fails) {
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.locator('.chat-history-item.active')).toHaveText(A.title)
    await expect(page.getByText(/^A 24 /)).toBeAttached()
    await expect(draft).toHaveValue('Проверить адресата')
  } else {
    await expect(page.getByText(/^B 24 /)).toBeAttached()
    await expect(draft).toHaveValue('')
    await draft.fill('Проверить адресата')
  }
  await expect(draft).toBeEnabled()
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect.poll(() => admitted).toEqual([
    `/api/v1/chat/threads/${fails ? A.id : B.id}/requests`,
  ])
})

test('SSE text growth keeps a reader at their earlier position', async ({ page }) => {
  await setup(page, [A])
  const requestId = '33333333-3333-4333-8333-333333333333'
  const streamed = 'Продолжение ответа. '.repeat(90)
  const assistant = partial(requestId, '99')
  let completed = false
  const delayedStatus = gate()
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({ json: {
    thread: A, messages: [...messages('A'), { ...assistant,
      content: completed ? streamed : '', state: completed ? 'complete' : 'partial' }],
  } }))
  await page.route(`**/api/v1/chat/requests/${requestId}`, async route => {
    await delayedStatus.wait
    return route.fulfill({ json: { id: requestId, thread_id: A.id, state: 'streaming' } })
  })
  await page.route(`**/api/v1/chat/requests/${requestId}/events`, route => {
    completed = true
    return route.fulfill({ headers: { 'content-type': 'text/event-stream' },
      body: `event: text.delta\ndata: ${JSON.stringify({ text: streamed })}\n\nevent: message.completed\ndata: {}\n\n` })
  })
  await page.goto('/')
  const requested = page.waitForRequest(`**/api/v1/chat/requests/${requestId}`)
  await choose(page, A.title)
  await requested
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await scroll(page).evaluate(node => { node.scrollTop = 200 })
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(180)
  delayedStatus.release()
  await expect(page.getByText(/^Продолжение ответа/)).toBeAttached()
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeLessThanOrEqual(240)
})

test('content growth follows only a reader near the end', async ({ page }) => {
  await setup(page, [A])
  await page.route(`**/api/v1/chat/threads/${A.id}`, route => route.fulfill({
    json: { thread: A, messages: messages('A') },
  }))
  await page.goto('/')
  await choose(page, A.title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await scroll(page).evaluate(node => {
    const extra = document.createElement('div')
    extra.textContent = 'Streaming content '.repeat(60)
    node.querySelector('.chat-turns')!.append(extra)
  })
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await scroll(page).evaluate(node => { node.scrollTop = 200 })
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(180)
  await scroll(page).evaluate(node => {
    const extra = document.createElement('div')
    extra.textContent = 'More streaming content '.repeat(60)
    node.querySelector('.chat-turns')!.append(extra)
  })
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeLessThanOrEqual(240)
  await scroll(page).evaluate(node => { node.scrollTop = node.scrollHeight })
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await scroll(page).evaluate(node => {
    const extra = document.createElement('div')
    extra.textContent = 'Final streaming content '.repeat(60)
    node.querySelector('.chat-turns')!.append(extra)
  })
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
})
