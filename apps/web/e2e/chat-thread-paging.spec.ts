import { expect, test } from '@playwright/test'
import { workspace } from './workspace-fixtures'

function gate() {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  return { wait, release }
}

test('older chats appear once on sidebar and drawer and reload starts at first page', async ({ page }) => {
  await workspace(page)
  const threads = Array.from({ length: 51 }, (_, index) => ({
    id: `11111111-1111-4111-8111-${(index + 1).toString().padStart(12, '0')}`,
    title: `Разговор ${index + 1}`, created_at: 1, updated_at: 52 - index,
  }))
  let olderCalls = 0
  await page.route('**/api/v1/chat/threads*', route => {
    const cursor = new URL(route.request().url()).searchParams.get('cursor')
    if (cursor) {
      expect(cursor).toBe('next-page')
      olderCalls++
      return route.fulfill({ json: { threads: [threads[49], threads[50]], next_cursor: null } })
    }
    return route.fulfill({ json: { threads: threads.slice(0, 50), next_cursor: 'next-page' } })
  })
  await page.goto('/')
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  const side = page.locator('.chat-sidebar')
  await expect(side.getByRole('button', { name: 'Разговор 51' })).toHaveCount(0)
  await side.getByRole('button', { name: 'Загрузить ранние чаты' }).click()
  await expect(side.getByRole('button', { name: 'Разговор 51' })).toHaveCount(1)
  await expect(side.getByRole('button', { name: 'Разговор 50' })).toHaveCount(1)
  await expect(side.getByRole('button', { name: 'Загрузить ранние чаты' })).toHaveCount(0)
  expect(olderCalls).toBe(1)
  await page.reload()
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  await expect(page.locator('.chat-sidebar').getByRole('button', { name: 'Разговор 51' })).toHaveCount(0)
})

test('refresh cancels an older page and keeps only the fresh cursor', async ({ page }) => {
  await workspace(page)
  const thread = { id: '11111111-1111-4111-8111-111111111133', title: 'Текущий чат',
    created_at: 1, updated_at: 1 }
  const stale = { ...thread, id: '11111111-1111-4111-8111-111111111134', title: 'Устаревший чат' }
  const delayed = gate()
  let firstPageCalls = 0
  await page.route('**/api/v1/chat/threads*', async route => {
    const url = new URL(route.request().url())
    if (url.searchParams.has('cursor')) {
      await delayed.wait
      return route.fulfill({ json: { threads: [stale], next_cursor: null } }).catch(() => {})
    }
    firstPageCalls++
    return route.fulfill({ json: { threads: [thread], next_cursor: 'more' } })
  })
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({
    json: { thread, messages: [], next_before_sequence: null },
  }))
  await page.route(`**/api/v1/chat/threads/${thread.id}/requests`, route => route.fulfill({
    status: 202, json: { id: route.request().postDataJSON().request_id, state: 'pending' },
  }))
  await page.route('**/api/v1/chat/requests/*/events', route => route.fulfill({
    headers: { 'content-type': 'text/event-stream' }, body: 'event: message.completed\ndata: {}\n\n',
  }))
  await page.goto('/')
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  await page.getByRole('button', { name: thread.title }).click()
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  await page.getByRole('button', { name: 'Загрузить ранние чаты' }).click()
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.locator('.chat-sidebar').getByRole('button', { name: 'Скрыть панель' }).click()
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Проверка')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect.poll(() => firstPageCalls).toBeGreaterThanOrEqual(2)
  delayed.release()
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  await expect(page.getByRole('button', { name: stale.title })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Загрузить ранние чаты' })).toBeEnabled()
})

test('pending older page cannot appear after Chat unmount and reload', async ({ page }) => {
  await workspace(page)
  const thread = { id: '11111111-1111-4111-8111-111111111135', title: 'Старый чат',
    created_at: 1, updated_at: 1 }
  const delayed = gate()
  let olderStarted = false
  await page.route('**/api/v1/chat/threads*', async route => {
    if (new URL(route.request().url()).searchParams.has('cursor')) {
      olderStarted = true
      await delayed.wait
      return route.fulfill({ json: { threads: [thread], next_cursor: null } }).catch(() => {})
    }
    return route.fulfill({ json: { threads: [], next_cursor: 'more' } })
  })
  await page.goto('/')
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  await page.getByRole('button', { name: 'Загрузить ранние чаты' }).click()
  await expect.poll(() => olderStarted).toBe(true)
  await page.reload()
  delayed.release()
  await expect(page.getByRole('button', { name: thread.title })).toHaveCount(0)
})
