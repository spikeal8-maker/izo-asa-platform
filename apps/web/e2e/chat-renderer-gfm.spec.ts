import { expect, test } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const thread = { id: '11111111-1111-4111-8111-111111111131', title: 'Renderer', created_at: 1, updated_at: 2 }
const message = (content: string, state: 'partial' | 'complete' = 'complete') => ({
  id: '22222222-2222-4222-8222-222222222222', request_id: '33333333-3333-4333-8333-333333333333',
  role: 'assistant', sequence: 1, content, state, attachments: [], created_at: 1, updated_at: 1,
})

test.beforeEach(({}, info) => test.skip(!['phone-small', 'laptop'].includes(info.project.name)))

test('renders GFM table and task lists inside the message bounds without unsafe content', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [thread] } }))
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: {
    thread, messages: [message(`| Name | ${'Wide '.repeat(35)} |\n| --- | --- |\n| Alpha | Value |\n\n- [x] Done\n  - [ ] Nested next\n- [ ] Next\n\n<script>alert(1)</script>\n\n[Unsafe](javascript:alert(1))\n\n![Remote](https://example.invalid/image.png)`) ],
    next_before_sequence: null,
  } }))
  await page.goto('/')
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) {
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  }
  await page.getByRole('button', { name: thread.title }).click()
  await expect(page.locator('.chat-table-scroll table tbody tr')).toHaveCount(1)
  await expect(page.locator('.chat-assistant-message input[type="checkbox"]')).toHaveCount(3)
  await expect(page.locator('.chat-assistant-message input[type="checkbox"]').first()).toBeChecked()
  await expect(page.locator('.chat-assistant-message input[type="checkbox"]').last()).toBeDisabled()
  const nesting = await page.locator('.chat-assistant-message .task-list-item').first().evaluate(node => {
    const child = node.querySelector(':scope > ul > li')
    const parentBox = node.getBoundingClientRect()
    const childBox = child?.getBoundingClientRect()
    return { nested: Boolean(child), below: Boolean(childBox && childBox.top > parentBox.top) }
  })
  expect(nesting).toEqual({ nested: true, below: true })
  await expect(page.locator('.chat-assistant-message script')).toHaveCount(0)
  await expect(page.locator('.chat-assistant-message a[href^="javascript:"]')).toHaveCount(0)
  await expect(page.locator('.chat-assistant-message img')).toHaveCount(0)
  const geometry = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    table: document.querySelector('.chat-table-scroll')!.scrollWidth - document.querySelector('.chat-table-scroll')!.clientWidth,
  }))
  expect(geometry.document).toBeLessThanOrEqual(1)
  expect(geometry.table).toBeGreaterThan(0)
})

test('unfinished GFM content can be replaced by the final saved answer', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [thread] } }))
  let content = '| Name | Status |\n| ---'
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: {
    thread, messages: [message(content, content.endsWith('---') ? 'partial' : 'complete')], next_before_sequence: null,
  } }))
  await page.goto('/')
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) {
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  }
  await page.getByRole('button', { name: thread.title }).click()
  await expect(page.locator('.chat-assistant-message')).toContainText('Name')
  content = '| Name | Status |\n| --- | --- |\n| Final | Done |'
  await page.reload()
  if (await page.getByRole('button', { name: 'Открыть панель' }).isVisible()) {
    await page.getByRole('button', { name: 'Открыть панель' }).click()
  }
  await page.getByRole('button', { name: thread.title }).click()
  await expect(page.locator('.chat-table-scroll tbody')).toContainText('Final')
})
