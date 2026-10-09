import { expect, test } from '@playwright/test'
import { workspace } from './workspace-fixtures'

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
