import { expect, type Page } from '@playwright/test'
import { branches, editFixture, gate, uid } from './chat-message-edit-fixture'
import type { ThreadView } from '../src/shared/api'

export { gate }
export const side = (page: Page) => page.locator('.chat-sidebar')
export const input = (page: Page) => side(page).getByRole('textbox', { name: 'Поиск по чатам', exact: true })
export const rows = (page: Page) => side(page).locator('.chat-history-item')
export const status = (page: Page) => side(page).getByRole('status', { name: 'Результаты поиска' })
export const results = (page: Page, text: string) => expect(status(page)).toHaveText(text)
export const more = (page: Page) => side(page).getByRole('button', { name: 'Загрузить ещё результаты', exact: true })
export const earlier = (page: Page) => side(page).getByRole('button', { name: 'Загрузить ранние чаты', exact: true })
export const retry = (page: Page) => side(page).getByRole('button', { name: 'Повторить поиск', exact: true })
export const alert = (page: Page) => side(page).getByRole('alert')
export const profile = (page: Page) => side(page).getByRole('button', { name: 'Профиль в боковой панели' })
export async function savedGraph(page: Page, branch: string) {
  await expect(page.getByText('Сохранённый выбранный ответ', { exact: true })).toBeVisible()
  await expect(page.getByText('Третья сохранённая ветка', { exact: true })).toBeVisible()
  await expect(branches(page)).toHaveValue(branch)
}
export async function openSide(page: Page) {
  if (await side(page).getAttribute('aria-hidden') === 'true')
    await page.getByRole('button', { name: 'Открыть панель', exact: true }).click()
}
export async function search(page: Page, query: string) {
  await openSide(page)
  if (!await input(page).count()) await side(page).getByRole('button', { name: 'Поиск чатов', exact: true }).click()
  await input(page).fill(query)
}
export async function settled(page: Page) {
  // A paint barrier checks the DOM after a deliberately late fetch has completed.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
}
export async function releaseRead(page: Page, pause: ReturnType<typeof gate>, query: string, cursor = false) {
  const response = page.waitForResponse(result => {
    const url = new URL(result.url())
    return url.searchParams.get('q') === query && url.searchParams.has('cursor') === cursor
  })
  pause.release()
  await (await response).finished()
  await settled(page)
}
type Read = { q: string; cursor: string | null; owner: string }
type Rule = { q: string; cursor?: string | null; pause?: ReturnType<typeof gate>;
  failure?: string; status?: number; network?: boolean }

export async function searchFixture(page: Page, ignoreAbort = false) {
  if (ignoreAbort) await page.addInitScript(() => {
    const fetch = window.fetch
    window.fetch = (url, options) => {
      const parsed = new URL(String(url), location.origin)
      // Simulate a transport which still delivers after cancellation; fences must suffice.
      return fetch(url, parsed.pathname === '/api/v1/chat/threads' && parsed.searchParams.has('q')
        ? { ...options, signal: undefined } : options)
    }
  })
  const graph = await editFixture(page)
  const original = graph.active().turns
  graph.fork(original[1].id, 'Вторая сохранённая ветка')
  graph.switchTo(graph.root.id)
  graph.fork(original[2].id, 'Третья сохранённая ветка')
  const first = graph.active().turns[0], variant = structuredClone(first.attempts[0])
  variant.id = uid(800001); variant.request_id = uid(800002); variant.ordinal = 2
  variant.message = { ...variant.message, id: uid(800003), request_id: variant.request_id, content: 'Сохранённый выбранный ответ' }
  first.attempts.push(variant); first.selected_attempt_id = variant.id
  graph.requests.set(variant.request_id, { branch: graph.state.active, turn: first, attempt: variant })
  graph.thread.title = 'Архив IZO %_\\ сохранённые ветки'
  const threads: ThreadView[] = Array.from({ length: 151 }, (_, index) => index === 150 ? graph.thread : ({
    id: uid(900000 + index), title: `${index >= 48 ? 'Архив IZO' : 'Другая серия'} ${index + 1}`,
    created_at: 2000 - index, updated_at: 2000 - index,
  }))
  const state = { threads, reads: [] as Read[], finished: [] as Read[], rules: [] as Rule[],
    overrides: new Map<string, ThreadView[]>(), otherThreads: [] as ThreadView[], patches: 0,
    patchPause: null as ReturnType<typeof gate> | null, patchFailure: '', owner: graph.app.account.id }
  await page.route('**/api/v1/auth/logout', async route => {
    expect(route.request().headers()['x-csrf-token']).toBe('workspace-csrf')
    graph.app.signedIn = false
    await route.fulfill({ status: 204 })
  })
  await page.route('**/api/v1/chat/threads**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const json = (data: unknown, code = 200) => route.fulfill({ json: data, status: code }).catch(() => {})
    if (request.method() === 'PATCH' && /^\/api\/v1\/chat\/threads\/[^/]+$/.test(path)) {
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      const thread = threads.find(item => path.endsWith(item.id))!
      state.patches++
      await state.patchPause?.wait
      if (state.patchFailure) return json({ error: { code: state.patchFailure } }, 422)
      thread.title = request.postDataJSON().title
      return json(thread)
    }
    if (path !== '/api/v1/chat/threads' || request.method() !== 'GET') return route.fallback()
    const q = url.searchParams.get('q') ?? '', cursor = url.searchParams.get('cursor')
    const read = { q, cursor, owner: graph.app.account.id }
    state.reads.push(read)
    const ruleIndex = state.rules.findIndex(rule => rule.q === q && (rule.cursor === undefined || rule.cursor === cursor))
    const rule = ruleIndex < 0 ? undefined : state.rules.splice(ruleIndex, 1)[0]
    const prefix = q ? `s:${encodeURIComponent(q)}:` : 'h:'
    const offset = cursor ? Number(cursor.slice(prefix.length)) : 0
    expect(!cursor || cursor.startsWith(prefix)).toBe(true)
    const owned = read.owner === state.owner ? threads : state.otherThreads
    // Synthetic literal examples only; exhaustive Unicode/matcher proof belongs to server tests.
    const found = state.overrides.get(q) ?? (q ? owned.filter(item => item.title.toLowerCase().includes(q.trim().toLowerCase())) : owned)
    const snapshot = structuredClone({ threads: found.slice(offset, offset + 50),
      next_cursor: offset + 50 < found.length ? `${prefix}${offset + 50}` : null })
    await rule?.pause?.wait
    if (rule?.network) await route.abort('failed').catch(() => {})
    else if (rule?.failure) await json({ error: { code: rule.failure } }, rule.status ?? 503)
    else await json(snapshot)
    state.finished.push(read)
  })
  await page.goto('/')
  await openSide(page)
  await expect(rows(page)).toHaveCount(50)
  return { ...graph, data: state }
}
