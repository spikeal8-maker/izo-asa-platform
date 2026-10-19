import { expect, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

export function gate() {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  return { wait, release }
}
export const side = (page: Page) => page.locator('.chat-sidebar')
export const row = (page: Page, title: string) => page.locator('.chat-history-row').filter({
  has: page.getByRole('button', { name: title, exact: true }),
})
export async function openSide(page: Page) {
  const opener = page.getByRole('button', { name: 'Открыть панель' })
  if (await opener.isVisible()) await opener.click()
}
export async function fixture(page: Page, count = 1, credentialsWait?: Promise<void>) {
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
export async function rename(page: Page, oldTitle: string, newTitle: string) {
  await row(page, oldTitle).getByRole('button', { name: 'Переименовать', exact: true }).click()
  await page.getByRole('textbox', { name: 'Название чата', exact: true }).fill(newTitle)
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
}
export async function send(page: Page) {
  if (await side(page).getAttribute('role') === 'dialog')
    await side(page).getByRole('button', { name: 'Скрыть панель' }).click()
  await page.getByRole('textbox', { name: 'Сообщение', exact: true }).fill('Проверка')
  await page.getByRole('button', { name: 'Отправить', exact: true }).click()
}
