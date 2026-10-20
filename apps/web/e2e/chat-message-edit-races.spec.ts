import { expect, test, type Page } from '@playwright/test'
import { branches, editFixture, editRow, editor, gate, openEditThread, uid } from './chat-message-edit-fixture'

const composer = (page: Page) => page.getByRole('textbox', { name: 'Сообщение', exact: true })
const send = (page: Page) => page.getByRole('button', { name: 'Отправить', exact: true })
const retry = (page: Page) => page.getByRole('button', { name: 'Обновить ветку', exact: true })
const check = (page: Page) => page.getByRole('button', { name: 'Проверить отправку', exact: true })
const save = (page: Page) => page.getByRole('button', { name: 'Сохранить и отправить', exact: true })
async function open(page: Page) { await page.goto('/'); await openEditThread(page) }
async function beginEdit(page: Page, id: string, text = 'Новая версия') {
  await editRow(page, id).getByRole('button', { name: 'Изменить' }).click()
  await editor(page).fill(text); await save(page).click()
}

test('UNKNOWN survives A to B and reload, independently of branch-local rows', async ({ page }) => {
  const fixture = await editFixture(page)
  const root = fixture.active(), child = fixture.fork(root.turns[0].id, 'Другая ветка')
  fixture.switchTo(root.meta.id)
  fixture.state.unknown = root.turns[0].attempts[0].request_id
  await open(page)
  await expect(page.getByRole('alert')).toContainText('Результат у провайдера неизвестен')
  await branches(page).selectOption(child.meta.id)
  await expect(page.getByText('Другая ветка', { exact: true })).toBeVisible()
  await expect(page.getByText('Вопрос 1', { exact: true })).toHaveCount(0)
  await page.reload(); await openEditThread(page)
  await expect(branches(page)).toHaveValue(child.meta.id)
  await expect(page.getByRole('alert')).toContainText('Результат у провайдера неизвестен')
  await expect(send(page)).toBeDisabled()
  await expect(editRow(page, child.edited.user_message.id).getByRole('button', { name: 'Изменить' })).toBeDisabled()
  expect(fixture.state.events).toHaveLength(0)
  expect(fixture.state.commands.every(item => item.path.endsWith('/branch-selection'))).toBe(true)
})

for (const operation of ['edit', 'switch', 'send'] as const) test(`${operation}: accepted change and failed Graph reload stays closed until read retry`, async ({ page }) => {
  const fixture = await editFixture(page)
  const root = fixture.active(), source = root.turns[1]
  const child = fixture.fork(source.id, 'Сохранённая дочерняя ветка')
  fixture.switchTo(root.meta.id)
  await open(page); await composer(page).fill('Сохранённый черновик')
  if (operation === 'switch') {
    fixture.state.graphFailures = 1
    await branches(page).selectOption(child.meta.id)
  } else {
    fixture.state.pause[operation] = gate()
    if (operation === 'edit') await beginEdit(page, source.user_message.id)
    else await send(page).click()
    await expect.poll(() => fixture.state.commands.length).toBe(1)
    fixture.finish(fixture.state.commands[0].body.request_id)
    fixture.state.graphFailures = 1
    fixture.state.pause[operation]!.release()
  }
  await expect(retry(page)).toBeVisible()
  await expect(send(page)).toBeDisabled()
  await expect(branches(page)).toBeDisabled()
  await expect(composer(page)).toHaveValue(operation === 'send' ? '' : 'Сохранённый черновик')
  expect(fixture.state.commands).toHaveLength(1)
  await retry(page).click()
  await expect(branches(page)).toBeEnabled()
  await expect(retry(page)).toHaveCount(0)
  expect(fixture.state.events).toHaveLength(0)
  expect(fixture.state.commands).toHaveLength(1)
})

test('every cached range is reread at one revision before any new execution', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await editFixture(page, 60), root = fixture.active()
  const child = fixture.fork(root.turns[59].id, 'Дочерний конец')
  fixture.switchTo(root.meta.id)
  await open(page)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения', exact: true }).click()
  await expect(page.locator('.chat-turn-user')).toHaveCount(60)
  await branches(page).selectOption(child.meta.id)
  await expect(branches(page)).toBeEnabled()
  fixture.state.onGraph = before => {
    if (!before) return
    const turn = root.turns[0], next = structuredClone(turn.attempts[0])
    next.id = uid(800001); next.ordinal = 2; next.message.content = 'Свежий выбранный префикс'
    turn.attempts.push(next); turn.selected_attempt_id = next.id
    fixture.state.revision++; fixture.state.onGraph = () => {}
  }
  fixture.state.pause.graph = gate(); fixture.state.graphDelayAt = fixture.state.graphReads + 2
  await branches(page).selectOption(root.meta.id)
  await expect.poll(() => fixture.state.graphReads).toBe(fixture.state.graphDelayAt)
  await expect(send(page)).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Изменить' }).first()).toBeDisabled()
  fixture.state.pause.graph.release()
  await expect(page.locator('.chat-turn-user')).toHaveCount(60)
  await expect(page.getByText('Свежий выбранный префикс', { exact: true })).toBeVisible()
  await expect(branches(page)).toBeEnabled()
  await composer(page).fill('Теперь можно отправить')
  await send(page).click()
  await expect.poll(() => fixture.state.commands.filter(item => item.path.endsWith('/requests')).length).toBe(1)
  const command = fixture.state.commands.find(item => item.path.endsWith('/requests'))!
  expect(command.body.branch_id).toBe(root.meta.id)
  expect(command.body.expected_revision).toBeGreaterThan(5)
})

test('switching cached branches of different depth retains the shared reading anchor', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await editFixture(page, 102), root = fixture.active()
  const child = fixture.fork(root.turns[101].id, 'Новый конец')
  fixture.switchTo(root.meta.id)
  await open(page)
  await expect(page.locator('.chat-turn-user')).toHaveCount(50)
  await branches(page).selectOption(child.meta.id)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения', exact: true }).click()
  await expect(page.locator('.chat-turn-user')).toHaveCount(100)
  const anchor = editRow(page, root.turns[80].user_message.id)
  await branches(page).selectOption(root.meta.id)
  await expect(branches(page)).toBeEnabled()
  await expect(page.locator('.chat-turn-user')).toHaveCount(50)
  await anchor.scrollIntoViewIfNeeded()
  const before = (await anchor.boundingBox())!.y
  await anchor.evaluate(node => { (node as HTMLElement).dataset.identity = 'shared' })
  await branches(page).selectOption(child.meta.id)
  await expect(branches(page)).toBeEnabled()
  await expect(page.locator('.chat-turn-user')).toHaveCount(100)
  await expect(anchor).toHaveAttribute('data-identity', 'shared')
  await expect.poll(async () => Math.abs((await anchor.boundingBox())!.y - before)).toBeLessThan(4)
})

for (const replay of ['edit', 'regenerate']) test(`accepted ${replay} UUID after another branch: identity retained, no reactivation or terminal SSE`, async ({ page }) => {
  const fixture = await editFixture(page), root = fixture.active(), source = root.turns[0]
  fixture.state.abort = replay
  await open(page)
  if (replay === 'edit') await beginEdit(page, source.user_message.id)
  else await page.locator(`[data-turn-id="${source.id}"]`).getByRole('button', { name: 'Ответить заново' }).click()
  await expect(check(page)).toBeVisible()
  const original = fixture.state.commands[0].body
  fixture.finish(original.request_id)
  const acceptedBranch = fixture.state.active
  fixture.switchTo(root.meta.id)
  const later = fixture.fork(root.turns[0].id, 'Последняя активная ветка')
  await retry(page).click()
  await expect(branches(page)).toHaveValue(later.meta.id)
  await expect(page.getByText('Последняя активная ветка', { exact: true })).toBeVisible()
  await check(page).click()
  await expect(check(page)).toHaveCount(0)
  await expect(branches(page)).toHaveValue(later.meta.id)
  expect(fixture.state.commands.filter(item => item.path.endsWith(`/${replay}`)).map(item => item.body)).toEqual([original, original])
  expect(fixture.state.active).toBe(later.meta.id)
  expect(fixture.state.events).toHaveLength(0)
  expect(fixture.requests.has(original.request_id)).toBe(true)
  expect(acceptedBranch).not.toBe(later.meta.id)
})

for (const inherited of [false, true]) test(`delayed modern regeneration receipt ${inherited ? 'from child prefix' : 'from excluded root'} cannot start a terminal old request`, async ({ page }) => {
  const fixture = await editFixture(page), root = fixture.active()
  if (inherited) fixture.fork(root.turns[2].id, 'Первый дочерний конец')
  const source = fixture.active().turns[0], executionBranch = fixture.state.active
  fixture.state.pause.regenerate = gate()
  await open(page)
  await page.locator(`[data-turn-id="${source.id}"]`).getByRole('button', { name: 'Ответить заново' }).click()
  await expect.poll(() => fixture.state.commands.length).toBe(1)
  const request = fixture.state.commands[0].body.request_id
  fixture.finish(request)
  const later = fixture.fork(source.id, 'Более поздняя ветка')
  fixture.state.pause.regenerate.release()
  await expect(branches(page)).toHaveValue(later.meta.id)
  await expect(page.getByText('Более поздняя ветка', { exact: true })).toBeVisible()
  expect(fixture.requests.get(request)!.branch).toBe(executionBranch)
  expect(fixture.state.events).toHaveLength(0)
  expect(fixture.state.commands).toHaveLength(1)
})

test('an uncertain ordinary send checks its frozen A intent after a coherent B reload', async ({ page }) => {
  const fixture = await editFixture(page), root = fixture.active()
  fixture.state.abort = 'send'
  let unavailable = true
  await page.route('**/api/v1/chat/requests/*', route => unavailable
    ? route.fulfill({ status: 503, json: { error: { code: 'unavailable' } } }) : route.fallback())
  await open(page); await composer(page).fill('Тот же запрос')
  await send(page).click()
  await expect(page.getByRole('alert')).toContainText('Приём неизвестен')
  const original = fixture.state.commands[0].body
  fixture.finish(original.request_id)
  const child = fixture.fork(root.turns[0].id, 'Активна B')
  await retry(page).click()
  await expect(branches(page)).toHaveValue(child.meta.id)
  unavailable = false
  await send(page).click()
  await expect(composer(page)).toHaveValue('')
  await expect(branches(page)).toHaveValue(child.meta.id)
  expect(fixture.state.commands.filter(item => item.path.endsWith('/requests'))).toHaveLength(1)
  expect(fixture.state.requestReads).toContain(original.request_id)
  expect(fixture.state.events).toHaveLength(0)
})

for (const failure of [false, true]) test(`fresh send CAS conflict reconciles without resending; reload failure=${failure}`, async ({ page }) => {
  const fixture = await editFixture(page), root = fixture.active()
  const child = fixture.fork(root.turns[0].id, 'Новый активный контекст')
  fixture.switchTo(root.meta.id)
  await open(page); await composer(page).fill('Сохранить мой ввод')
  fixture.switchTo(child.meta.id)
  if (failure) fixture.state.graphFailures = 1
  await send(page).click()
  if (failure) {
    await expect(send(page)).toBeDisabled()
    await expect(retry(page)).toBeVisible()
    await retry(page).click()
  }
  await expect(branches(page)).toHaveValue(child.meta.id)
  await expect(page.getByText('Новый активный контекст', { exact: true })).toBeVisible()
  await expect(composer(page)).toHaveValue('Сохранить мой ввод')
  await expect(send(page)).toBeEnabled()
  expect(fixture.state.commands).toHaveLength(1)
  expect(fixture.state.events).toHaveLength(0)
})
