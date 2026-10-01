import { expect, test, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const threads = [
  { id: '11111111-1111-4111-8111-111111111131', title: 'Длинный разговор A', created_at: 1, updated_at: 2 },
  { id: '11111111-1111-4111-8111-111111111132', title: 'Длинный разговор B', created_at: 1, updated_at: 2 },
]
const messages = (label: string) => Array.from({ length: 25 }, (_, index) => ({
  id: `22222222-2222-4222-8222-${String(index + (label === 'A' ? 0 : 100)).padStart(12, '0')}`,
  role: 'user', sequence: index + 1, content: `${label} ${index} ` + 'Длинная строка разговора. '.repeat(12),
  state: 'complete', created_at: 1, updated_at: 1,
}))
const scroll = (page: Page) => page.locator('.chat-scroll')
const distanceFromBottom = (page: Page) => scroll(page).evaluate(node =>
  node.scrollHeight - node.clientHeight - node.scrollTop)

async function choose(page: Page, title: string) {
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) {
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  }
  await page.getByRole('button', { name: title }).click()
}

test('delayed history load and A→B→A restore the reader viewport', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads } }))
  let releaseB!: () => void
  const waitB = new Promise<void>(resolve => { releaseB = resolve })
  await page.route('**/api/v1/chat/threads/*', async route => {
    const thread = threads.find(item => route.request().url().endsWith(item.id))!
    if (thread === threads[1]) await waitB
    await route.fulfill({ json: { thread, messages: messages(thread === threads[0] ? 'A' : 'B') } })
  })
  await page.goto('/')
  await choose(page, threads[0].title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await scroll(page).evaluate(node => { node.scrollTop = 220 })
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(200)
  await choose(page, threads[1].title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  expect(await scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(200)
  releaseB()
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  await expect.poll(() => distanceFromBottom(page)).toBeLessThanOrEqual(2)
  await choose(page, threads[0].title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(200)
  expect(await scroll(page).evaluate(node => node.scrollTop)).toBeLessThanOrEqual(240)
})

for (const staleFails of [false, true]) test(`latest selected thread ignores late ${staleFails ? 'error' : 'response'}`, async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads } }))
  let enteredA!: () => void
  const requestedA = new Promise<void>(resolve => { enteredA = resolve })
  let releaseA!: () => void
  const waitA = new Promise<void>(resolve => { releaseA = resolve })
  await page.route('**/api/v1/chat/threads/*', async route => {
    const isA = route.request().url().endsWith(threads[0].id)
    if (isA) {
      enteredA()
      await waitA
      if (staleFails) return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    }
    const thread = isA ? threads[0] : threads[1]
    return route.fulfill({ json: { thread, messages: messages(isA ? 'A' : 'B') } })
  })
  await page.goto('/')
  await choose(page, threads[0].title)
  await requestedA
  await choose(page, threads[1].title)
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  const staleSettled = page.waitForEvent('requestfinished', request => request.url().endsWith(threads[0].id))
  releaseA()
  await staleSettled
  await expect(page.getByText(/^B 24 /)).toBeAttached()
  await expect(page.getByText(/^A 24 /)).toHaveCount(0)
  await expect(page.locator('.chat-history-item.active')).toHaveText(threads[1].title)
  await expect(page.getByRole('alert')).toHaveCount(0)
})

for (const fails of [false, true]) test(`opening a thread ${fails ? 'fails safely' : 'cannot send to the old thread'}`, async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  await workspace(page)
  const admitted: string[] = []
  let releaseB!: () => void
  const waitB = new Promise<void>(resolve => { releaseB = resolve })
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads } }))
  await page.route('**/api/v1/chat/threads/*', async route => {
    const isB = route.request().url().endsWith(threads[1].id)
    if (isB) await waitB
    if (isB && fails) return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    const thread = isB ? threads[1] : threads[0]
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
  await choose(page, threads[0].title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  const draft = page.getByRole('textbox', { name: 'Сообщение' })
  await draft.fill('Проверить адресата')
  await choose(page, threads[1].title)
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await expect(draft).toBeDisabled()
  await page.locator('.chat-composer').evaluate(form => (form as HTMLFormElement).requestSubmit())
  expect(await draft.inputValue()).toBe('Проверить адресата')
  expect(admitted).toEqual([])
  releaseB()
  if (fails) {
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.locator('.chat-history-item.active')).toHaveText(threads[0].title)
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
    `/api/v1/chat/threads/${fails ? threads[0].id : threads[1].id}/requests`,
  ])
})

test('SSE text growth keeps a reader at their earlier position', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  await workspace(page)
  const requestId = '33333333-3333-4333-8333-333333333333'
  const streamed = 'Продолжение ответа. '.repeat(90)
  const assistant = { id: '22222222-2222-4222-8222-222222222299', request_id: requestId,
    role: 'assistant', sequence: 26, content: '', state: 'partial', created_at: 1, updated_at: 1 }
  let completed = false
  let entered!: () => void
  const requested = new Promise<void>(resolve => { entered = resolve })
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [threads[0]] } }))
  await page.route(`**/api/v1/chat/threads/${threads[0].id}`, route => route.fulfill({ json: {
    thread: threads[0], messages: [...messages('A'), { ...assistant,
      content: completed ? streamed : '', state: completed ? 'complete' : 'partial' }],
  } }))
  await page.route(`**/api/v1/chat/requests/${requestId}`, async route => {
    entered()
    await gate
    return route.fulfill({ json: { id: requestId, thread_id: threads[0].id, state: 'streaming' } })
  })
  await page.route(`**/api/v1/chat/requests/${requestId}/events`, route => {
    completed = true
    return route.fulfill({ headers: { 'content-type': 'text/event-stream' },
      body: `event: text.delta\ndata: ${JSON.stringify({ text: streamed })}\n\nevent: message.completed\ndata: {}\n\n` })
  })
  await page.goto('/')
  await choose(page, threads[0].title)
  await requested
  await expect(page.getByText(/^A 24 /)).toBeAttached()
  await scroll(page).evaluate(node => { node.scrollTop = 200 })
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeGreaterThanOrEqual(180)
  release()
  await expect(page.getByText(/^Продолжение ответа/)).toBeAttached()
  await expect.poll(() => scroll(page).evaluate(node => node.scrollTop)).toBeLessThanOrEqual(240)
})

test('content growth follows only a reader near the end', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [threads[0]] } }))
  await page.route(`**/api/v1/chat/threads/${threads[0].id}`, route => route.fulfill({
    json: { thread: threads[0], messages: messages('A') },
  }))
  await page.goto('/')
  await choose(page, threads[0].title)
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
