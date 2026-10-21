import { expect, test } from '@playwright/test'
import { noOverflow } from './workspace-fixtures'
import { alert, earlier, gate, input, more, openSide, profile, releaseRead, results, retry, rows, savedGraph,
  search, searchFixture, settled, side, status } from './chat-thread-search-fixture'

test.beforeEach(({}, info) => test.skip(!['phone-small', 'laptop'].includes(info.project.name), 'Search boundary on touch and desktop'))

test('finds the 151st title via raw literal query and opens saved Graph selections after reload', async ({ page }) => {
  const fixture = await searchFixture(page), raw = '  %_\\  '
  expect(fixture.data.threads.indexOf(fixture.thread)).toBe(150)
  await expect(side(page).getByRole('button', { name: fixture.thread.title, exact: true })).toHaveCount(0)
  await search(page, raw)
  await results(page, 'Найдено: 1')
  expect(fixture.data.reads.filter(read => read.q).map(read => read.q)).toEqual([raw])
  await rows(page).click()
  await savedGraph(page, fixture.state.active)
  expect(fixture.state.commands).toEqual([])
  await page.reload(); await openSide(page)
  await expect(input(page)).toHaveCount(0)
  await expect(rows(page)).toHaveCount(50)
  await search(page, raw); await results(page, 'Найдено: 1')
  await rows(page).click()
  await savedGraph(page, fixture.state.active)
})

test('paginates 103 matches, retries failed page and restores ordinary pages, cursor and scroll', async ({ page }) => {
  const fixture = await searchFixture(page), query = 'Архив IZO'
  await earlier(page).click(); await expect(rows(page)).toHaveCount(100)
  const ids = await rows(page).evaluateAll(elements => elements.map(element => element.id))
  const list = side(page).locator('.chat-history-list')
  await list.evaluate(element => { element.scrollTop = 237 })
  const scroll = await list.evaluate(element => element.scrollTop)
  await search(page, query); await results(page, 'Показано: 50')
  fixture.data.rules.push({ q: query, cursor: `s:${encodeURIComponent(query)}:50`, failure: 'search_unavailable' })
  await more(page).click()
  await expect(alert(page)).toHaveText('Поиск временно недоступен. Повторите попытку.')
  await expect(rows(page)).toHaveCount(50)
  const failed = fixture.data.reads.at(-1)!
  await retry(page).click(); await results(page, 'Показано: 100')
  expect(fixture.data.reads.at(-1)).toEqual(failed)
  await more(page).click(); await results(page, 'Найдено: 103')
  expect(new Set(await rows(page).evaluateAll(elements => elements.map(element => element.id))).size).toBe(103)
  await expect(more(page)).toHaveCount(0)
  await input(page).fill('')
  await expect(rows(page)).toHaveCount(100)
  expect(await rows(page).evaluateAll(elements => elements.map(element => element.id))).toEqual(ids)
  await expect.poll(() => list.evaluate(element => element.scrollTop)).toBe(scroll)
  await earlier(page).click(); await expect(rows(page)).toHaveCount(150)
  expect(fixture.data.reads.at(-1)?.cursor).toBe('h:100')
  await earlier(page).click(); await expect(rows(page)).toHaveCount(151)
})

test('first-page overload is distinct from empty and never retries automatically', async ({ page }) => {
  const fixture = await searchFixture(page), query = 'Архив'
  await page.clock.install()
  fixture.data.rules.push({ q: query, failure: 'search_unavailable' })
  await search(page, query)
  await expect(alert(page)).toContainText('Поиск временно недоступен')
  await expect(status(page)).toHaveCount(0); await expect(rows(page)).toHaveCount(0)
  const count = fixture.data.reads.length
  await page.clock.fastForward(20000)
  expect(fixture.data.reads.length).toBe(count)
  await retry(page).click(); await results(page, 'Показано: 50')
  await input(page).fill('Нет такого чата'); await results(page, 'Чаты не найдены')
  await expect(retry(page)).toHaveCount(0)
  await input(page).fill('😀'.repeat(257))
  await expect(input(page)).toHaveValue('😀'.repeat(257))
  await expect(input(page)).toHaveAttribute('aria-invalid', 'true')
  await expect(alert(page)).toContainText('256')
  const previous = fixture.data.reads.length
  await input(page).fill('😀'.repeat(256)); await results(page, 'Чаты не найдены')
  expect(fixture.data.reads.length).toBe(previous + 1)
  expect(fixture.data.reads.at(-1)?.q).toBe('😀'.repeat(256))
  await input(page).fill(query); await results(page, 'Показано: 50')
  fixture.data.rules.push({ q: query, cursor: `s:${encodeURIComponent(query)}:50`, failure: 'auth_required', status: 401 })
  await more(page).click(); await expect(alert(page)).toContainText('Войдите в аккаунт')
  await expect(rows(page)).toHaveCount(0); await expect(more(page)).toHaveCount(0)
  await noOverflow(page)
})

test('aborts an obsolete request and ignores its late result after a new query', async ({ page }) => {
  const fixture = await searchFixture(page), pause = gate()
  fixture.data.rules.push({ q: 'Архив', pause })
  const cancelled = page.waitForEvent('requestfailed', request => new URL(request.url()).searchParams.get('q') === 'Архив')
  await search(page, 'Архив'); await results(page, 'Ищем чаты…')
  await expect.poll(() => fixture.data.reads.at(-1)?.q).toBe('Архив')
  await input(page).fill('Другая'); await cancelled
  await results(page, 'Найдено: 48')
  pause.release(); await expect.poll(() => fixture.data.finished.some(read => read.q === 'Архив')).toBe(true)
  await settled(page); await results(page, 'Найдено: 48')
})

test('late A success and error cannot overwrite B even if the transport ignores abort', async ({ page }) => {
  const fixture = await searchFixture(page, true)
  for (const failure of [undefined, 'search_unavailable']) {
    const pause = gate(), query = failure ? 'Архив IZO' : 'Архив'
    fixture.data.rules.push({ q: query, pause, failure })
    await search(page, query); await expect.poll(() => fixture.data.reads.at(-1)?.q).toBe(query)
    await input(page).fill('Другая'); await results(page, 'Найдено: 48')
    if (!failure) {
      fixture.data.overrides.set(query, [fixture.thread])
      await input(page).fill(query); await results(page, 'Найдено: 1')
    }
    await releaseRead(page, pause, query)
    await results(page, failure ? 'Найдено: 48' : 'Найдено: 1')
    await expect(alert(page)).toHaveCount(0)
    if (failure) expect((await rows(page).allTextContents()).every(title => title.startsWith('Другая'))).toBe(true)
    fixture.data.overrides.delete(query)
  }
  await input(page).fill('Архив'); await results(page, 'Показано: 50')
  const pause = gate()
  fixture.data.rules.push({ q: 'Архив', cursor: `s:${encodeURIComponent('Архив')}:50`, pause })
  await more(page).click(); await expect.poll(() => fixture.data.reads.at(-1)?.cursor).not.toBeNull()
  await input(page).fill('Другая'); await results(page, 'Найдено: 48')
  await releaseRead(page, pause, 'Архив', true)
  await expect(rows(page)).toHaveCount(48); await expect(more(page)).toHaveCount(0)
})

test('late overload after clear or logout cannot paint; another account starts with its own history', async ({ page }) => {
  const fixture = await searchFixture(page, true)
  for (const logout of [false, true]) {
    const pause = gate(), query = logout ? 'Архив IZO' : 'Архив'
    fixture.data.rules.push({ q: query, pause, failure: 'search_unavailable' })
    await search(page, query); await expect.poll(() => fixture.data.reads.at(-1)?.q).toBe(query)
    if (logout) {
      await profile(page).click()
      await side(page).getByRole('menuitem', { name: 'Выйти' }).click()
      await expect(page.getByRole('button', { name: 'Профиль в боковой панели' })).toHaveCount(0)
    } else { await input(page).fill(''); await expect(rows(page)).toHaveCount(50) }
    await releaseRead(page, pause, query)
    await expect(alert(page)).toHaveCount(0)
    if (logout) await expect(rows(page)).toHaveCount(0)
    else await expect(earlier(page)).toBeVisible()
  }
  fixture.app.account.id = '33333333-3333-4333-8333-333333333333'; fixture.app.signedIn = true
  fixture.data.otherThreads = [{ ...fixture.thread, id: '33333333-3333-4333-8333-333333333334', title: 'Чат другого аккаунта' }]
  await page.reload(); await openSide(page)
  await expect(rows(page)).toHaveText(['Чат другого аккаунта'])
  await search(page, 'Архив'); await results(page, 'Чаты не найдены')
  expect(fixture.data.reads.at(-1)?.owner).toBe(fixture.app.account.id)
})

test('confirmed rename keeps its form until save, refreshes membership and fences a held page', async ({ page }) => {
  const fixture = await searchFixture(page, true), pause = gate()
  await search(page, 'Архив'); await results(page, 'Показано: 50')
  fixture.data.rules.push({ q: 'Архив', cursor: `s:${encodeURIComponent('Архив')}:50`, pause })
  await more(page).click(); await expect.poll(() => fixture.data.reads.at(-1)?.cursor).not.toBeNull()
  const row = side(page).locator('.chat-history-row').first()
  await row.getByRole('button', { name: 'Переименовать', exact: true }).click()
  const editor = page.getByRole('textbox', { name: 'Название чата', exact: true })
  fixture.data.patchFailure = 'invalid_input'
  await editor.fill('Другое название'); await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.getByRole('form', { name: 'Переименование чата' }).getByRole('alert')).toBeVisible()
  await expect(rows(page).first()).toHaveText('Архив IZO 49')
  fixture.data.patchFailure = ''; fixture.data.patchPause = gate()
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect.poll(() => fixture.data.patches).toBe(2)
  await expect(editor).toHaveValue('Другое название'); await expect(editor).toHaveAttribute('readonly', '')
  fixture.data.patchPause.release()
  await expect(editor).toHaveCount(0); await results(page, 'Показано: 50')
  await expect(rows(page).first()).toHaveText('Архив IZO 50')
  await expect(input(page)).toBeFocused()
  await releaseRead(page, pause, 'Архив', true)
  await expect(rows(page)).toHaveCount(50); await results(page, 'Показано: 50')
  await expect(side(page).getByRole('button', { name: 'Другое название', exact: true })).toHaveCount(0)
  await input(page).fill(''); await expect(side(page).getByRole('button', { name: 'Другое название', exact: true })).toHaveCount(1)
})

test('cursor rejection recovers from page one; server membership, keyboard and drawer remain authoritative', async ({ page }) => {
  const fixture = await searchFixture(page), query = 'Архив'
  await search(page, query); await results(page, 'Показано: 50')
  fixture.data.rules.push({ q: query, cursor: `s:${encodeURIComponent(query)}:50`, failure: 'invalid_thread_cursor', status: 400 })
  await more(page).click(); await expect(alert(page)).toContainText('первой страницы')
  await retry(page).click(); await results(page, 'Показано: 50')
  expect(fixture.data.reads.at(-1)?.cursor).toBeNull()
  fixture.data.overrides.set('Серверное соответствие', [fixture.thread])
  await input(page).fill('Серверное соответствие'); await expect(rows(page)).toHaveText([fixture.thread.title])
  await input(page).press('Escape')
  const opener = side(page).getByRole('button', { name: 'Поиск чатов', exact: true })
  await expect(opener).toBeFocused(); await expect(rows(page)).toHaveCount(50)
  if (page.viewportSize()!.width < 1120) {
    await page.keyboard.press('Escape'); await expect(page.getByRole('button', { name: 'Открыть панель' })).toBeFocused()
    await page.getByRole('button', { name: 'Открыть панель' }).tap()
    await opener.tap()
  } else await opener.click()
  await expect(input(page)).toBeFocused(); await expect(input(page)).toHaveValue('')
  await profile(page).click()
  await side(page).getByRole('menuitemradio', { name: 'Тёмная' }).click()
  await noOverflow(page)
})
