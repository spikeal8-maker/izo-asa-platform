import { expect, test } from '@playwright/test'
import { answer, gate, graphFixture, openGraphThread, regenerateButton, previousButton, nextButton } from './conversation-graph-fixture'

for (const recovery of ['reload', 'admission replay']) test(`${recovery}: a streaming paid marker resumes the same request`, async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.state.eventGate = gate(); fixture.state.abortAdmission = recovery === 'admission replay'
  await page.goto('/'); await openGraphThread(page)
  await regenerateButton(page).click()
  const record = fixture.records[0]
  if (recovery === 'reload') {
    await expect.poll(() => fixture.state.events).toBe(1)
  } else {
    await expect(answer(page).getByRole('button', { name: 'Проверить запрос', exact: true })).toBeVisible()
    // Another consumer started the accepted request before this tab recovered admission.
    record.attempts[1].state = 'streaming'; record.attempts[1].error_code = 'provider_outcome_unknown'
  }
  const accepted = record.attempts[1]
  expect(fixture.graph().active_attempt).toMatchObject({ request_id: accepted.request_id,
    state: 'streaming', error_code: 'provider_outcome_unknown' })
  expect(fixture.graph().unknown_request_id).toBeNull()
  if (recovery === 'reload') { await page.reload(); await openGraphThread(page) }
  else await answer(page).getByRole('button', { name: 'Проверить запрос', exact: true }).click()
  await expect.poll(() => fixture.state.events).toBe(recovery === 'reload' ? 2 : 1)
  await expect(answer(page)).toContainText('Готовим новый вариант')
  await expect(answer(page)).toContainText('Ответ 1, вариант 1')
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(fixture.state.requestReads).toBe(1)
  expect(fixture.state.commands).toHaveLength(1)
  expect(accepted.request_id).toBe(fixture.state.commands[0].body.request_id)
  fixture.state.eventGate.release()
  await expect(answer(page)).toContainText('Ответ 1, вариант 2')
  await expect(answer(page)).toContainText('2 из 2')
  await expect(regenerateButton(page)).toHaveAttribute('aria-disabled', 'false')
  expect(record.attempts).toHaveLength(2)
  expect(accepted.error_code).toBeNull()
})

test('fresh revision conflict refreshes selection without repeating a command', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant()
  await page.goto('/'); await openGraphThread(page)
  await expect(answer(page)).toContainText('Ответ 1, вариант 1')
  await expect(nextButton(page)).toHaveAttribute('aria-disabled', 'false')
  fixture.records[0].selected_attempt_id = fixture.records[0].attempts[1].id
  fixture.state.revision++
  await nextButton(page).click()
  await expect(answer(page)).toContainText('Ответ 1, вариант 2')
  await expect(answer(page)).toContainText('Выбор уже изменился')
  expect(fixture.state.commands).toHaveLength(1)
})

test('an uncertain selection reads persisted state and preserves deliberate composer focus', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant(); fixture.state.abortSelection = true
  const attemptsGate = gate(), graphGate = gate()
  fixture.state.graphGate = graphGate; fixture.state.graphDelayAt = 2
  let attemptsRequested = false
  // Establish actual focus before recovery can temporarily disable the composer.
  await page.route(/\/turns\/[^/]+\/attempts(?:\?|$)/, async route => {
    attemptsRequested = true; await attemptsGate.wait; await route.fallback()
  })
  try {
    await page.goto('/'); await openGraphThread(page)
    await nextButton(page).click()
    const input = page.getByRole('textbox', { name: 'Сообщение', exact: true })
    await expect.poll(() => attemptsRequested).toBe(true)
    await expect(input).toBeEnabled()
    await input.focus()
    await expect(input).toBeFocused()
    attemptsGate.release()
    await expect.poll(() => fixture.state.graphReads).toBe(2)
    await expect(input).toBeDisabled()
    graphGate.release()
    await expect(answer(page)).toContainText('Ответ 1, вариант 2')
    await expect(input).toBeFocused()
    expect(fixture.state.commands).toHaveLength(1)
  } finally {
    attemptsGate.release(); graphGate.release()
  }
})

for (const outcome of ['completed', 'interrupted', 'error', 'stopped']) test(`${outcome}: late selection respects commit order and terminal lifecycle`, async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant(); fixture.records[0].selected_attempt_id = fixture.records[0].attempts[1].id
  fixture.state.eventGate = gate(); fixture.state.selectionGate = gate()
  fixture.state.outcome = outcome; fixture.state.terminalRevision = outcome === 'completed'
  await page.goto('/'); await openGraphThread(page)
  await regenerateButton(page).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  await previousButton(page).click()
  await expect.poll(() => fixture.state.commands.length).toBe(2)
  fixture.state.eventGate.release()
  await expect(answer(page)).toContainText(outcome === 'completed' ? 'Ответ 1, вариант 3' : 'Ответ 1, вариант 1')
  await answer(page).evaluate(node => new MutationObserver(() => {
    if (node.textContent?.includes('Готовим новый вариант')) (node as HTMLElement).dataset.regressed = 'true'
  }).observe(node, { childList: true, subtree: true, characterData: true }))
  const late = page.waitForResponse(response => response.url().endsWith('/selection'))
  fixture.state.selectionGate.release()
  await (await late).finished()
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  await expect(answer(page)).toContainText(outcome === 'completed' ? '3 из 3' : '1 из 2')
  await expect(answer(page)).not.toHaveAttribute('data-regressed', 'true')
  expect(fixture.state.requestReads).toBe(0)
})

test('a late selection response cannot replace a different selected thread', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant(); fixture.state.selectionGate = gate()
  await page.goto('/'); await openGraphThread(page)
  await nextButton(page).click()
  await expect.poll(() => fixture.state.commands.length).toBe(1)
  await openGraphThread(page, fixture.other.title)
  await expect(page.getByText('Сообщение другого чата', { exact: true })).toBeVisible()
  fixture.state.selectionGate.release()
  await expect(page.locator('.chat-turn-assistant')).toHaveCount(0)
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('a graph page captured before a newer selection cannot restore an older answer', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant(); fixture.records[0].selected_attempt_id = fixture.records[0].attempts[1].id
  fixture.state.eventGate = gate(); fixture.state.graphGate = gate(); fixture.state.graphDelayAt = 2
  await page.goto('/'); await openGraphThread(page)
  await regenerateButton(page).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  fixture.state.eventGate.release()
  await expect.poll(() => fixture.state.graphReads).toBe(2)
  await previousButton(page).click()
  await expect(answer(page)).toContainText('3 из 3')
  await previousButton(page).click()
  await expect(answer(page)).toContainText('2 из 3')
  fixture.state.graphGate.release()
  await expect(page.getByRole('button', { name: 'Отправить', exact: true })).toBeVisible()
  await expect(answer(page)).toContainText('Ответ 1, вариант 2')
  await expect(answer(page)).not.toContainText('Ответ 1, вариант 3')
})

for (const outcome of ['interrupted', 'error', 'stopped']) test(`${outcome}: an older page cannot revive an off-page terminal attempt`, async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await graphFixture(page, 53)
  fixture.addVariant()
  const pending = fixture.records[0].attempts[1]
  pending.state = 'pending'; pending.message.state = 'partial'; pending.message.content = ''
  fixture.state.outcome = outcome; fixture.state.terminalRevision = false
  fixture.state.eventGate = gate(); fixture.state.graphGate = gate(); fixture.state.graphDelayAt = 2
  await page.goto('/'); await openGraphThread(page)
  await expect.poll(() => fixture.state.events).toBe(1)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения', exact: true }).click()
  await expect.poll(() => fixture.state.graphReads).toBe(2)
  fixture.state.eventGate.release()
  await expect(page.getByRole('button', { name: 'Отправить', exact: true })).toBeVisible()
  await expect(answer(page)).toHaveCount(0)
  const turns = page.locator('.chat-turns')
  await turns.evaluate(node => new MutationObserver(() => {
    if (node.textContent?.includes('Готовим новый вариант')) (node as HTMLElement).dataset.regressed = 'true'
  }).observe(node, { childList: true, subtree: true, characterData: true }))
  fixture.state.graphGate.release()
  await expect(page.locator('.chat-turn-user')).toHaveCount(53)
  await expect(answer(page)).toContainText(outcome === 'error' ? 'Новый вариант не получен'
    : 'Результат нового запроса уточняется')
  await expect(turns).not.toHaveAttribute('data-regressed', 'true')
  expect(fixture.state.requestReads).toBe(1)
  expect(fixture.state.events).toBe(1)
})

test('late SSE bytes and errors cannot overwrite a Graph-confirmed completed answer', async ({ page }) => {
  const fixture = await graphFixture(page)
  fixture.addVariant(); fixture.records[0].selected_attempt_id = fixture.records[0].attempts[1].id
  fixture.state.eventGate = gate()
  await page.goto('/'); await openGraphThread(page)
  await regenerateButton(page).click()
  await expect.poll(() => fixture.state.events).toBe(1)
  const completed = fixture.records[0].attempts.at(-1)!
  completed.state = 'completed'; completed.error_code = null; completed.message.state = 'complete'
  completed.message.content = 'Полный сохранённый ответ B'
  fixture.records[0].selected_attempt_id = completed.id; fixture.state.revision++
  await previousButton(page).click()
  await expect(answer(page)).toContainText(completed.message.content)
  await answer(page).evaluate(node => new MutationObserver(() => {
    if (node.textContent?.includes('Запоздавший фрагмент')) (node as HTMLElement).dataset.regressed = 'true'
  }).observe(node, { childList: true, subtree: true, characterData: true }))
  fixture.state.delayedEvents = 'event: text.delta\ndata: {"text":"Запоздавший фрагмент"}\n\n'
    + 'event: message.error\ndata: {"code":"provider_rejected"}\n\n'
  fixture.state.eventGate.release()
  await expect(page.getByRole('button', { name: 'Отправить', exact: true })).toBeVisible()
  await expect(answer(page)).not.toHaveAttribute('data-regressed', 'true')
  await expect(answer(page)).toContainText(completed.message.content)
  await expect(page.getByRole('alert')).toHaveCount(0)
})
