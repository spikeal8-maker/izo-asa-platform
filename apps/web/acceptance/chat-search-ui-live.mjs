// Shared real-browser history, search and unchanged Graph assertions.
import { expect } from '@playwright/test'
import { button, command } from './chat-message-edit-live.mjs'

const marker = 'Архив IZO', other = 'Другая серия', literal = '%_\\'
const textbox = (page, name) => page.getByRole('textbox', { name, exact: true })
const input = page => textbox(page, 'Поиск по чатам')
const composer = page => textbox(page, 'Сообщение')
const viewports = [['desktop', 1440, 900], ['phone', 390, 844]]
const side = page => page.locator('.chat-sidebar'), scroll = page => page.locator('.chat-history-list')
const rows = page => page.locator('.chat-history-item')
const ids = threads => threads.map(thread => thread.id)
const uiIds = page => rows(page).evaluateAll(items => items.map(item => item.id.replace('chat-history-', '')))
const path = (q, cursor) => `threads?${new URLSearchParams({ ...(q === null ? {} : { q }), ...(cursor ? { cursor } : {}) })}`
const listReply = (page, q, cursor = null) => page.waitForResponse(response => {
  const url = new URL(response.url())
  return response.request().method() === 'GET' && url.pathname === '/api/v1/chat/threads'
    && url.searchParams.get('q') === q && url.searchParams.get('cursor') === cursor
})
async function decoded(response) {
  expect(response.status()).toBe(200)
  return response.json()
}
async function checkRows(page, expected) {
  await expect.poll(() => uiIds(page)).toEqual(expected)
  expect(new Set(expected).size).toBe(expected.length)
}
async function panel(page) {
  if (await side(page).getAttribute('aria-hidden') === 'true') await button(page, 'Открыть панель').click()
  await expect(side(page)).toHaveAttribute('aria-hidden', 'false')
}
async function query(page, q) {
  await panel(page)
  if (!await input(page).count()) {
    await button(side(page), 'Поиск чатов').click()
    await expect(input(page)).toBeFocused()
  }
  if (await input(page).inputValue() === q) await input(page).fill('')
  const waiting = listReply(page, q)
  await input(page).fill(q)
  const result = await decoded(await waiting)
  await checkRows(page, ids(result.threads))
  return result
}
async function more(page, q, cursor, expected) {
  expect(cursor).toBeTruthy()
  const previous = await uiIds(page)
  expect(previous).toEqual(expected.slice(0, previous.length))
  const waiting = listReply(page, q, cursor)
  await button(side(page), q === null ? 'Загрузить ранние чаты' : 'Загрузить ещё результаты').click()
  const result = await decoded(await waiting)
  expect(ids(result.threads)).toEqual(expected.slice(previous.length))
  await checkRows(page, expected)
  return result
}
async function pages(page, q, count) {
  const threads = [], cursors = [], lengths = []
  let cursor = null
  for (let start = 0; start < count; start += 50) {
    const result = await command(page, path(q, cursor))
    expect(result.threads).toHaveLength(Math.min(50, count - start))
    threads.push(...result.threads); lengths.push(result.threads.length)
    cursor = result.next_cursor; cursors.push(cursor)
    if (start + 50 < count) expect(cursor).toBeTruthy()
  }
  expect(cursor).toBeNull(); expect(new Set(ids(threads)).size).toBe(count)
  return { threads, cursors, lengths }
}
async function rename(page, oldTitle, title) {
  const row = page.locator('.chat-history-row').filter({ has: button(page, oldTitle) })
  const id = (await row.locator('.chat-history-item').getAttribute('id')).replace('chat-history-', '')
  const q = await input(page).count() ? await input(page).inputValue() : ''
  const refreshed = q.trim() ? listReply(page, q) : null
  const saved = page.waitForResponse(response => response.request().method() === 'PATCH'
    && new URL(response.url()).pathname === `/api/v1/chat/threads/${id}`)
  await button(row, 'Переименовать').click()
  await textbox(page, 'Название чата').fill(title)
  await button(page, 'Сохранить').click()
  expect((await decoded(await saved)).title).toBe(title)
  await expect(textbox(page, 'Название чата')).toHaveCount(0)
  if (refreshed) await checkRows(page, ids((await decoded(await refreshed)).threads))
  else await expect(button(page, title)).toBeVisible()
}
async function logout(page) {
  await panel(page); await button(side(page), 'Профиль в боковой панели').click()
  const waiting = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/auth/logout')
  await page.getByRole('menuitem', { name: 'Выйти', exact: true }).click()
  expect((await waiting).ok()).toBe(true)
  await expect(button(page, 'Профиль')).toHaveCount(0)
  await expect(rows(page)).toHaveCount(0)
}
async function snapshot(page, proof) {
  const base = `threads/${proof.thread_id}`, graph = await command(page, `${base}/graph`)
  const branches = await command(page, `${base}/branches`), detail = await command(page, base)
  expect(graph.active_branch_id).toBe(proof.active_branch_id)
  expect(graph.turns).toEqual(proof.projections[proof.active_branch_id])
  expect(branches.branches).toHaveLength(3); expect(branches.branches).toEqual(proof.branches)
  expect(detail.messages).toEqual(proof.physical_messages)
  return { graph, branches, detail }
}
async function geometry(page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}
async function searchHistory(page, proof, ordinary, matches, phase, folder) {
  const evidence = [], target = ordinary.threads[proof.target], draft = 'Search draft'
  for (const [name, width, height] of viewports) {
    await page.setViewportSize({ width, height }); await page.reload(); await panel(page)
    await checkRows(page, proof.ids.slice(0, 50))
    let result = await query(page, marker)
    expect(ids(result.threads)).toEqual(matches.slice(0, 50))
    for (const count of [100, 103]) result = await more(page, marker, result.next_cursor, matches.slice(0, count))
    expect(result.next_cursor).toBeNull()
    await page.locator(`#chat-history-${target.id}`).scrollIntoViewIfNeeded()
    await geometry(page)
    await page.screenshot({ path: `${folder}/search-${phase}-${name}-${new URL(page.url()).port}.png`, animations: 'disabled' })
    await input(page).fill(''); await checkRows(page, proof.ids.slice(0, 50))
    for (let index = 0; index < 2; index++)
      await more(page, null, ordinary.cursors[index], proof.ids.slice(0, (index + 2) * 50))
    const selected = page.locator(`#chat-history-${proof.ids[0]}`)
    if (name === 'phone') await selected.tap()
    else { await selected.focus(); await selected.press('Enter') }
    await composer(page).fill(draft)
    await panel(page)
    const position = await scroll(page).evaluate(element => { element.scrollTop = 420; return element.scrollTop })
    expect(position).toBeGreaterThan(100)
    await query(page, marker); await input(page).fill('')
    await checkRows(page, proof.ids.slice(0, 150))
    await expect.poll(() => scroll(page).evaluate((element, saved) => Math.abs(element.scrollTop - saved), position)).toBeLessThanOrEqual(1)
    await expect(page.locator('.chat-composer-dock textarea')).toHaveValue(draft)
    await expect(selected).toHaveClass(/\bactive\b/)
    await more(page, null, ordinary.cursors[2], proof.ids)
    const remaining = proof.ids.filter(id => !matches.includes(id)), final = listReply(page, other)
    for (const q of [marker, 'absent', other]) await input(page).fill(q)
    expect(ids((await decoded(await final)).threads)).toEqual(remaining)
    await checkRows(page, remaining)
    await expect(input(page)).toHaveValue(other)
    for (const q of literal) expect(ids((await query(page, q)).threads)).toEqual([proof.literal])
    await input(page).press('Escape')
    await expect(input(page)).toHaveCount(0); await expect(button(side(page), 'Поиск чатов')).toBeFocused()
    if (name === 'phone') {
      await page.keyboard.press('Escape'); await expect(button(page, 'Открыть панель')).toBeFocused()
      await expect(side(page)).toHaveAttribute('inert', '')
    }
    await geometry(page)
    evidence.push({ name, width, height, search: [50, 100, 103], ordinary: [50, 100, 150, 151], scroll: position })
  }
  return evidence
}
async function openGraph(page, proof, baseline, phase, folder) {
  for (const [name, width, height] of viewports) {
    await page.setViewportSize({ width, height }); await page.reload()
    const result = await query(page, proof.title)
    expect(ids(result.threads)).toEqual([proof.thread_id])
    const item = button(side(page), proof.title)
    if (name === 'phone') await item.tap()
    else { await item.focus(); await item.press('Enter') }
    await expect(page.getByRole('combobox', { name: 'Ветка разговора', exact: true })).toHaveValue(proof.active_branch_id)
    const turns = proof.projections[proof.active_branch_id]
    await expect(page.locator('.chat-turn-user')).toHaveCount(turns.length)
    for (const turn of turns) {
      await expect(page.locator(`[data-edit-message-id="${turn.user_message.id}"]`)).toContainText(turn.user_message.content)
      await expect(page.locator(`[data-turn-id="${turn.id}"]`)).toHaveAttribute('data-message-id', turn.selected_attempt.message.id)
    }
    expect(await snapshot(page, proof)).toEqual(baseline)
    await expect(composer(page)).toBeEnabled()
    await geometry(page)
    await page.screenshot({ path: `${folder}/search-open-${phase}-${name}-${new URL(page.url()).port}.png`, animations: 'disabled' })
  }
}
export { marker, other, literal, input, ids, path, checkRows, panel, query, pages, rename, logout, snapshot, searchHistory, openGraph }
