import { expect, test, type Page } from '@playwright/test'
import { editFixture, openEditThread } from './chat-message-edit-fixture'
import { answer, gate, graphFixture, openGraphThread, regenerateButton, previousButton, nextButton } from './conversation-graph-fixture'

function observeRanges(page: Page, threadId: string) {
  const ranges = new Map<string, { branch: string; revision: number; selected: unknown }>()
  page.on('response', async response => {
    const url = new URL(response.url())
    if (!url.pathname.endsWith(`/${threadId}/graph`)) return
    try {
      const page = await response.json()
      ranges.set(url.searchParams.get('before_turn_sequence') ?? 'head',
        { branch: page.active_branch_id, revision: page.revision, selected: page.turns[0]?.selected_attempt_id })
    } catch { /* Aborted response. */ }
  })
  return ranges
}

test('a pending first answer resumes through Graph and becomes its first selected variant', async ({ page }) => {
  const fixture = await graphFixture(page, 1), record = fixture.records[0]
  record.selected_attempt_id = null
  record.attempts[0].state = 'pending'; record.attempts[0].message.state = 'partial'
  record.attempts[0].message.content = ''; fixture.state.eventGate = gate()
  await page.goto('/'); await openGraphThread(page)
  await expect.poll(() => fixture.state.events).toBe(1)
  await expect(regenerateButton(page)).toHaveCount(0)
  fixture.state.eventGate.release()
  await expect(answer(page)).toContainText('Ответ 1, вариант 1')
  await expect(regenerateButton(page)).toBeVisible()
  expect(fixture.records[0].attempts).toHaveLength(1)
})

test('regeneration preserves the selected answer, draft and turn until durable completion', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.state.eventGate = gate()
  await page.goto('/'); await openGraphThread(page)
  const first = answer(page)
  await expect(first).toContainText('Ответ 1, вариант 1')
  await first.evaluate(node => { (node as HTMLElement).dataset.identity = 'same-turn' })
  const draft = page.getByRole('textbox', { name: 'Сообщение', exact: true })
  await draft.fill('Сохранить мой черновик')
  await regenerateButton(page).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  await expect(first).toContainText('Ответ 1, вариант 1')
  await expect(first).toContainText('Готовим новый вариант')
  await expect(page.locator('.chat-turn-user')).toHaveCount(2)
  fixture.state.eventGate.release()
  await expect(first).toContainText('Ответ 1, вариант 2')
  await expect(first).toContainText('2 из 2')
  await expect(first).toHaveAttribute('data-identity', 'same-turn')
  await expect(draft).toHaveValue('Сохранить мой черновик')
  await expect(page.locator('.chat-turn-assistant')).toHaveCount(2)
  await expect(answer(page, 2)).toContainText('Ответ 2, вариант 1')
  expect(fixture.state.commands.filter(item => item.path.endsWith('/regenerate'))).toHaveLength(1)
})

test('completed variants switch with keyboard, retain focus and survive reload', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant(); fixture.addVariant()
  await page.goto('/'); await openGraphThread(page)
  const first = answer(page), next = nextButton(page)
  await next.focus(); await next.press('Enter')
  await expect(first).toContainText('Ответ 1, вариант 2')
  await expect(next).toBeFocused()
  await next.press('Enter')
  await expect(first).toContainText('3 из 3')
  await expect(next).toBeFocused()
  await next.press('Enter')
  expect(fixture.state.commands).toHaveLength(2)
  await page.reload(); await openGraphThread(page)
  await expect(answer(page)).toContainText('Ответ 1, вариант 3')
  await previousButton(page).click()
  await expect(answer(page)).toContainText('2 из 3')
  expect(fixture.state.commands.at(-1)?.method).toBe('PATCH')
  expect(fixture.state.commands.map(item => item.body.expected_revision)).toEqual([3, 4, 5])
})

test('lost regeneration admission reconciles the same request without a second attempt', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.state.abortAdmission = true
  fixture.state.eventGate = gate()
  await page.goto('/'); await openGraphThread(page)
  await regenerateButton(page).click()
  await expect(answer(page).getByRole('button', { name: 'Проверить запрос', exact: true })).toBeVisible()
  const accepted = fixture.state.commands[0].body.request_id
  await answer(page).getByRole('button', { name: 'Проверить запрос', exact: true }).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  expect(fixture.records[0].attempts).toHaveLength(2)
  expect(fixture.records[0].attempts[1].request_id).toBe(accepted)
  fixture.state.eventGate.release()
  await expect(answer(page)).toContainText('Ответ 1, вариант 2')
  expect(fixture.state.commands.filter(item => item.path.endsWith('/regenerate'))).toHaveLength(1)
})

for (const outcome of ['error', 'interrupted', 'stopped']) test(`${outcome} keeps the previous completed variant`, async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.state.outcome = outcome
  fixture.state.eventGate = gate()
  await page.goto('/'); await openGraphThread(page)
  await regenerateButton(page).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  if (outcome === 'stopped') await page.getByRole('button', { name: 'Остановить ответ', exact: true }).click()
  else fixture.state.eventGate.release()
  await expect(answer(page)).toContainText('Ответ 1, вариант 1')
  await expect(answer(page)).toContainText(outcome === 'error' ? 'Новый вариант не получен'
    : 'Результат нового запроса уточняется')
  await expect(answer(page)).not.toContainText('2 из 2')
  if (outcome !== 'error') {
    await page.reload(); await openGraphThread(page)
    await expect(answer(page)).toContainText('Ответ 1, вариант 1')
    await expect(answer(page)).toContainText('Результат нового запроса уточняется')
    await expect(regenerateButton(page)).toHaveAttribute('aria-disabled', 'true')
    await regenerateButton(page).focus()
    await regenerateButton(page).press('Enter')
    expect(fixture.state.commands).toHaveLength(1)
    expect(fixture.state.events).toBe(1)
  }
})

test('old-turn regeneration preserves loaded pages, DOM order and the reading position', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await graphFixture(page, 53)
  const ranges = observeRanges(page, fixture.thread.id)
  await page.goto('/'); await openGraphThread(page)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения', exact: true }).click()
  await expect(page.locator('.chat-turn-user')).toHaveCount(53)
  const first = answer(page)
  await first.scrollIntoViewIfNeeded()
  await first.evaluate(node => { (node as HTMLElement).dataset.identity = 'original-turn' })
  fixture.state.eventGate = gate()
  await regenerateButton(page).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  const before = await first.boundingBox()
  fixture.state.eventGate.release()
  await expect(first).toContainText('Ответ 1, вариант 2')
  await expect(page.locator('.chat-turn-user')).toHaveCount(53)
  await expect.poll(async () => Math.abs(((await first.boundingBox())?.y ?? 0) - before!.y)).toBeLessThan(4)
  // Completion advances revision: every retained range must be reread before send.
  const coherent = { branch: fixture.state.branch, revision: fixture.state.revision }
  await expect.poll(() => [ranges.get('head'), ranges.get('4')]).toMatchObject([coherent, coherent])
  expect(ranges.get('4')?.selected).toBe(fixture.records[0].attempts[1].id)
  expect(fixture.state.olderReads).toBe(2)
  await expect(first).toHaveAttribute('data-identity', 'original-turn')
  expect(await page.locator('.chat-turn-user').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-message-id'))))
    .toEqual(fixture.records.map(record => record.user_message.id))
  await expect(page.locator('.chat-turn-assistant').first()).toHaveAttribute('data-turn-id', fixture.records[0].id)
})

test('head lifecycle lookup cannot discard a concurrently published older range at the same revision', async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await graphFixture(page, 100), first = fixture.records[0]
  fixture.addVariant()
  const pending = first.attempts[1], revision = fixture.state.revision
  pending.state = 'pending'; pending.message.state = 'partial'; pending.message.content = ''
  fixture.state.eventGate = gate(); fixture.state.outcome = 'interrupted'; fixture.state.terminalRevision = false
  const lookup = gate(), started = gate(), ranges = observeRanges(page, fixture.thread.id)
  await page.route(url => url.pathname.endsWith(`/${first.id}/attempts`), async route => {
    const snapshot = structuredClone({ ...fixture.turnState(first), attempts: first.attempts, next_before_ordinal: null })
    started.release(); await lookup.wait
    await route.fulfill({ json: snapshot })
  })
  await page.goto('/'); await openGraphThread(page)
  await expect(page.locator('.chat-turn-user')).toHaveCount(50)
  await expect.poll(() => fixture.state.events).toBe(1)
  fixture.state.graphGate = gate(); fixture.state.graphDelayAt = fixture.state.graphReads + 1
  await page.getByRole('button', { name: 'Загрузить ранние сообщения', exact: true }).click()
  await expect.poll(() => fixture.state.olderReads).toBe(1)
  pending.error_code = 'request_expired'; fixture.state.eventGate.release()
  await started.wait
  fixture.state.graphGate.release()
  await expect(page.locator('.chat-turn-user')).toHaveCount(100)
  await answer(page).evaluate(node => { (node as HTMLElement).dataset.identity = 'retained-range' })
  lookup.release()
  await expect.poll(() => fixture.state.olderReads).toBe(2)
  await expect(page.getByRole('textbox', { name: 'Сообщение', exact: true })).toBeEnabled()
  await expect(page.locator('.chat-turn-user')).toHaveCount(100)
  await expect(answer(page)).toHaveAttribute('data-identity', 'retained-range')
  expect(await page.locator('.chat-turn-user').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-message-id'))))
    .toEqual(fixture.records.map(record => record.user_message.id))
  expect(fixture.state.revision).toBe(revision)
  const coherent = { branch: fixture.state.branch, revision }
  await expect.poll(() => [ranges.get('head'), ranges.get('51')]).toMatchObject([coherent, coherent])
})

test('graph failure is explicit and controls stay inside mobile and desktop bounds', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant()
  await page.goto('/'); await openGraphThread(page)
  await expect(regenerateButton(page)).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  fixture.state.rejectRegenerate = 'model_not_allowed'
  await regenerateButton(page).click()
  await expect(answer(page)).toContainText('Выбранная модель не разрешена сервером')
  await expect(answer(page)).toContainText('Ответ 1, вариант 1')
  expect(fixture.state.events).toBe(0)
  await page.route('**/api/v1/chat/threads/*/graph', route => route.fulfill({ status: 503, json: { error: { code: 'unavailable' } } }))
  await page.reload(); await openGraphThread(page)
  await expect(page.getByRole('alert')).toContainText('Не удалось открыть чат')
  await expect(page.locator('.chat-turn-assistant')).toHaveCount(0)
})

test('same-branch regeneration UUID remains one execution after admission loss', async ({ page }) => {
  const fixture = await editFixture(page), source = fixture.active().turns[0]
  fixture.state.abort = 'regenerate'; fixture.state.pause.events = gate()
  await page.goto('/'); await openEditThread(page)
  await page.locator(`[data-turn-id="${source.id}"]`).getByRole('button', { name: 'Ответить заново' }).click()
  await page.getByRole('button', { name: 'Проверить отправку', exact: true }).click()
  await expect.poll(() => fixture.state.events.length).toBe(1)
  expect(source.attempts).toHaveLength(2)
  expect(fixture.state.commands).toHaveLength(1)
  fixture.state.pause.events.release()
  await expect(page.locator(`[data-turn-id="${source.id}"]`)).toContainText('2 из 2')
})
