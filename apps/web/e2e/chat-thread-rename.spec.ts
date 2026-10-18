import { expect, test, type Page } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'

function gate() {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  return { wait, release }
}
const side = (page: Page) => page.locator('.chat-sidebar')
const row = (page: Page, title: string) => page.locator('.chat-history-row').filter({
  has: page.getByRole('button', { name: title, exact: true }),
})
async function openSide(page: Page) {
  const opener = page.getByRole('button', { name: 'Открыть панель' })
  if (await opener.isVisible()) await opener.click()
}
async function fixture(page: Page, count = 1, credentialsWait?: Promise<void>) {
  await workspace(page)
  if (credentialsWait) await page.route('**/api/v1/chat/credentials', async route => {
    await credentialsWait
    return route.fulfill({ json: { credentials: [] } })
  })
  const state = {
    threads: Array.from({ length: count }, (_, index) => ({
      id: `11111111-1111-4111-8111-${String(index + 1).padStart(12, '0')}`,
      title: `Разговор ${index + 1}`, created_at: 1, updated_at: count - index,
    })),
    firstCalls: 0, detailCalls: 0, patches: 0, events: 0, failure: false,
    patchGate: null as ReturnType<typeof gate> | null,
    readGate: null as ReturnType<typeof gate> | null,
    eventGate: null as ReturnType<typeof gate> | null,
    delayRead: 0,
  }
  await page.route('**/api/v1/chat/threads**', async route => {
    const request = route.request(), url = new URL(request.url())
    const thread = state.threads.find(item => url.pathname.includes(item.id))
    if (request.method() === 'PATCH') {
      state.patches++
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      expect(request.headers()['x-izo-request']).toBe('web')
      expect(Object.keys(request.postDataJSON())).toEqual(['title'])
      if (state.failure) { state.failure = false; return route.abort('failed') }
      await state.patchGate?.wait
      thread!.title = request.postDataJSON().title
      return route.fulfill({ json: { ...thread } }).catch(() => {})
    }
    if (url.pathname.endsWith('/requests')) return route.fulfill({ status: 202, json: {
      id: request.postDataJSON().request_id, thread_id: thread!.id, state: 'pending',
    } })
    if (thread) {
      state.detailCalls++
      return route.fulfill({ json: { thread, messages: Array.from({ length: 20 }, (_, i) => ({
        id: `${thread.id}-${i}`, role: 'user', content: `Сохранённое сообщение ${i + 1}`,
        state: 'complete', sequence: i + 1, created_at: 1, updated_at: 1,
      })), next_before_sequence: null } })
    }
    const older = url.searchParams.has('cursor')
    if (!older) state.firstCalls++
    const snapshot = (older ? state.threads.slice(50) : state.threads.slice(0, 50)).map(item => ({ ...item }))
    if (!older && state.firstCalls === state.delayRead) await state.readGate?.wait
    return route.fulfill({ json: {
      threads: snapshot, next_cursor: !older && count > 50 ? 'older' : null,
    } }).catch(() => {})
  })
  await page.route('**/api/v1/chat/requests/*/events', async route => {
    state.events++
    await state.eventGate?.wait
    return route.fulfill({ headers: { 'content-type': 'text/event-stream' },
      body: 'event: message.completed\ndata: {}\n\n' }).catch(() => {})
  })
  await page.goto('/')
  await openSide(page)
  await expect(row(page, state.threads[0].title)).toBeVisible()
  return state
}
async function rename(page: Page, oldTitle: string, newTitle: string) {
  await row(page, oldTitle).getByRole('button', { name: 'Переименовать', exact: true }).click()
  await page.getByRole('textbox', { name: 'Название чата', exact: true }).fill(newTitle)
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
}
async function send(page: Page) {
  if (await side(page).getAttribute('role') === 'dialog')
    await side(page).getByRole('button', { name: 'Скрыть панель' }).click()
  await page.getByRole('textbox', { name: 'Сообщение', exact: true }).fill('Проверка')
  await page.getByRole('button', { name: 'Отправить', exact: true }).click()
}

test('rename updates an older row without losing pages, selection, messages or scroll and survives reload', async ({ page }, info) => {
  const state = await fixture(page, 52)
  await row(page, 'Разговор 1').getByRole('button', { name: 'Разговор 1', exact: true }).click()
  await expect(page.locator('.chat-turn-user')).toHaveCount(20)
  await page.locator('.chat-scroll').evaluate(node => { node.scrollTop = 240 })
  const messageScroll = await page.locator('.chat-scroll').evaluate(node => node.scrollTop)
  await openSide(page)
  await side(page).getByRole('button', { name: 'Загрузить ранние чаты' }).click()
  const target = row(page, 'Разговор 51')
  await target.scrollIntoViewIfNeeded()
  const before = await page.locator('.chat-history-list').evaluate(node => node.scrollTop)
  const reads = state.detailCalls
  await rename(page, 'Разговор 51', '  Урок робототехники  ')
  await expect(row(page, 'Урок робототехники')).toBeVisible()
  await expect(row(page, 'Урок робототехники').getByRole('button', { name: 'Переименовать', exact: true })).toBeFocused()
  await expect(page.locator('.chat-history-row')).toHaveCount(52)
  await expect(page.locator('.chat-history-item.active')).toHaveText('Разговор 1')
  await expect(page.locator('.chat-turn-user')).toHaveCount(20)
  expect(state.detailCalls).toBe(reads)
  expect(state.firstCalls).toBe(1)
  expect(await page.locator('.chat-scroll').evaluate(node => node.scrollTop)).toBe(messageScroll)
  expect(await page.locator('.chat-history-list').evaluate(node => node.scrollTop)).toBe(before)
  await send(page)
  await expect.poll(() => state.firstCalls).toBe(3)
  await openSide(page)
  await expect(page.locator('.chat-history-row')).toHaveCount(52)
  await expect(row(page, 'Урок робототехники')).toBeVisible()
  await expect(side(page).getByRole('button', { name: 'Загрузить ранние чаты' })).toHaveCount(0)
  await noOverflow(page)
  if ((page.viewportSize()?.width ?? 0) < 1120)
    await expect(side(page)).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 0, 0)')
  await page.screenshot({ path: info.outputPath('rename-saved.png'), fullPage: true, animations: 'disabled' })
  await page.reload(); await openSide(page)
  await side(page).getByRole('button', { name: 'Загрузить ранние чаты' }).click()
  await expect(row(page, 'Урок робототехники')).toBeVisible()
})

test('cancel and Escape restore focus; validation counts code points and a failed save keeps the draft', async ({ page }, info) => {
  const state = await fixture(page)
  const trigger = row(page, 'Разговор 1').getByRole('button', { name: 'Переименовать', exact: true })
  await trigger.click()
  const input = page.getByRole('textbox', { name: 'Название чата', exact: true })
  const save = page.getByRole('button', { name: 'Сохранить', exact: true })
  await expect(input).toBeFocused()
  for (const invalid of ['', ' \u3000\uFEFF ', '\u0085', '\u001c', '😀'.repeat(121), 'X\u0000']) {
    await input.fill(invalid); await expect(save).toBeDisabled()
  }
  await input.fill('😀'.repeat(120)); await expect(save).toBeEnabled()
  await page.keyboard.press('Escape')
  await expect(input).toHaveCount(0); await expect(trigger).toBeFocused()
  await expect(side(page)).toHaveAttribute('aria-hidden', 'false')
  expect(state.patches).toBe(0)
  await trigger.click(); await input.fill('Отменённый черновик')
  await page.getByRole('button', { name: 'Отмена', exact: true }).click()
  await expect(trigger).toBeFocused(); expect(state.patches).toBe(0)
  state.failure = true
  await rename(page, 'Разговор 1', 'Название после ошибки')
  await expect(page.getByRole('alert')).toContainText('Не удалось сохранить название')
  await expect(input).toHaveValue('Название после ошибки')
  await expect(row(page, 'Разговор 1')).toBeVisible()
  state.patchGate = gate()
  await input.press('Enter'); await input.press('Enter')
  await expect(page.getByRole('button', { name: 'Сохраняем…', exact: true })).toBeDisabled()
  await expect(input).toHaveAttribute('readonly', '')
  await expect.poll(() => state.patches).toBe(2)
  await page.screenshot({ path: info.outputPath('rename-pending.png'), fullPage: true })
  state.patchGate.release()
  await expect(row(page, 'Название после ошибки')).toBeVisible()
  await expect(row(page, 'Название после ошибки').getByRole('button', { name: 'Переименовать', exact: true })).toBeFocused()
})

for (const timing of ['before', 'during'] as const) {
  test(`a refresh started ${timing} PATCH cannot restore the old title; later fresh server titles remain visible`, async ({ page }) => {
    const state = await fixture(page)
    state.delayRead = 3; state.readGate = gate(); state.patchGate = gate()
    if (timing === 'during') state.eventGate = gate()
    await row(page, 'Разговор 1').getByRole('button', { name: 'Разговор 1', exact: true }).click()
    await send(page)
    await expect.poll(() => state.events).toBe(1)
    if (timing === 'before') await expect.poll(() => state.firstCalls).toBe(3)
    await openSide(page)
    await rename(page, 'Разговор 1', 'Сохранённое имя')
    await expect.poll(() => state.patches).toBe(1)
    state.eventGate?.release()
    await expect.poll(() => state.firstCalls).toBe(3)
    state.patchGate.release()
    await expect(row(page, 'Сохранённое имя')).toBeVisible()
    const response = page.waitForResponse(result => result.url().endsWith('/api/v1/chat/threads'))
    state.readGate.release(); await response
    await expect(row(page, 'Разговор 1')).toHaveCount(0)
    await expect(row(page, 'Сохранённое имя')).toBeVisible()
    state.threads[0].title = 'Имя из другой вкладки'
    await send(page)
    await expect.poll(() => state.firstCalls).toBeGreaterThanOrEqual(4)
    await openSide(page)
    await expect(row(page, 'Имя из другой вкладки')).toBeVisible()
  })
}

test('late credential initialization cannot undo a confirmed rename', async ({ page }) => {
  const delayed = gate()
  const state = await fixture(page, 1, delayed.wait)
  await rename(page, 'Разговор 1', 'Название до загрузки ключа')
  await expect(row(page, 'Название до загрузки ключа')).toBeVisible()
  const response = page.waitForResponse(result => result.url().endsWith('/api/v1/chat/credentials'))
  delayed.release(); await response
  await expect.poll(() => state.patches).toBe(1)
  await expect(row(page, 'Разговор 1')).toHaveCount(0)
})

test('pending rename after editor dismissal cannot steal focus or reopen private draft', async ({ page }) => {
  const state = await fixture(page)
  state.patchGate = gate()
  await rename(page, 'Разговор 1', 'Подтверждённое имя')
  await expect.poll(() => state.patches).toBe(1)
  await side(page).getByRole('button', { name: 'Скрыть панель' }).click()
  if ((page.viewportSize()?.width ?? 0) >= 1120)
    await side(page).getByRole('button', { name: 'Развернуть панель' }).click()
  else await openSide(page)
  await expect(page.getByRole('textbox', { name: 'Название чата', exact: true })).toHaveCount(0)
  const focus = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'))
  state.patchGate.release()
  await expect(row(page, 'Подтверждённое имя')).toBeVisible()
  expect(await page.evaluate(() => document.activeElement?.getAttribute('aria-label'))).toBe(focus)
  await row(page, 'Подтверждённое имя').getByRole('button', { name: 'Переименовать', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Название чата', exact: true })).toHaveValue('Подтверждённое имя')
})
