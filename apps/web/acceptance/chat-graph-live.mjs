// Ordinary authenticated HTTP/UI against the isolated fake-provider PostgreSQL stack.
// Concurrent client calls prove admission exclusion; DB lock overlap is separate QA.
import { randomUUID } from 'node:crypto'
import { expect } from '@playwright/test'

function isolated(page) {
  if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_CHAT_ACCEPTANCE !== 'isolated'
    || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(page.url()).hostname))
    throw new Error('Graph acceptance requires the explicit isolated loopback stack')
}
async function http(page, path, method = 'GET', data) {
  return page.evaluate(async ({ path, method, data }) => {
    const headers = { 'Content-Type': 'application/json', 'X-IZO-Request': 'web' }
    if (method !== 'GET') {
      const response = await fetch('/api/v1/auth/me', { credentials: 'same-origin', cache: 'no-store' })
      if (!response.ok) throw new Error('Graph acceptance authentication failed')
      headers['X-CSRF-Token'] = (await response.json()).csrf_token
    }
    const response = await fetch(`/api/v1/chat/${path}`, { method, headers,
      credentials: 'same-origin', cache: 'no-store', body: data === undefined ? undefined : JSON.stringify(data) })
    return { status: response.status, body: await response.json() }
  }, { path, method, data })
}
async function command(page, path, method = 'GET', data, status = 200) {
  const result = await http(page, path, method, data)
  expect(result.status, `${method} ${path}`).toBe(status)
  return result.body
}
const graph = (page, id) => command(page, `threads/${id}/graph`)
const turnPath = (id, turn) => `threads/${id}/turns/${turn.id}`
const row = (page, turn) => page.locator(`[data-turn-id="${turn.id}"]`)
async function complete(page, id) {
  const response = await page.evaluate(async id => {
    const result = await fetch(`/api/v1/chat/requests/${id}/events`, {
      credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'text/event-stream' },
    })
    return { status: result.status, type: result.headers.get('content-type'), body: await result.text() }
  }, id)
  expect(response.status).toBe(200)
  expect(response.type).toContain('text/event-stream')
  expect(response.body).toContain('event: message.completed')
  expect((await command(page, `requests/${id}`)).state).toBe('completed')
}
async function send(page, threadId, text, model) {
  const request = await command(page, `threads/${threadId}/requests`, 'POST', {
    request_id: randomUUID(), text, model, attachment_ids: [],
  }, 202)
  await complete(page, request.id)
  return request.id
}
async function open(page, title) {
  await page.reload()
  await expect(page.getByRole('textbox', { name: 'Сообщение', exact: true })).toBeVisible()
  const opener = page.getByRole('button', { name: 'Открыть панель', exact: true })
  if (await opener.isVisible()) await opener.click()
  await page.getByRole('button', { name: title, exact: true }).click()
}
const regeneration = (snapshot, turn) => ({ request_id: randomUUID(), branch_id: snapshot.active_branch_id,
  source_attempt_id: turn.selected_attempt_id, expected_revision: snapshot.revision })
const selection = (snapshot, attemptId) => ({ branch_id: snapshot.active_branch_id,
  attempt_id: attemptId, expected_revision: snapshot.revision })
const savedAttempts = attempts => attempts.map(({ id, request_id, ordinal, model, state, message }) =>
  ({ id, request_id, ordinal, model, state, message }))

export async function graphBefore(page, evidence) {
  isolated(page)
  const title = 'Сохранённые варианты Graph', policy = await command(page, 'policy')
  const thread = await command(page, 'threads', 'POST', { title }, 201)
  await send(page, thread.id, 'Первый вопрос Graph', policy.default_model)
  await send(page, thread.id, 'Поздний вопрос Graph', policy.default_model)
  const initial = await graph(page, thread.id), first = initial.turns[0], later = initial.turns[1]
  expect((await command(page, `threads/${thread.id}`)).graph_version).toBe(1)
  expect(initial.turns).toHaveLength(2)
  await open(page, title)
  const answer = row(page, first), draft = page.getByRole('textbox', { name: 'Сообщение', exact: true })
  await expect(answer).toHaveAttribute('data-message-id', first.selected_attempt.message.id)
  await draft.fill('Черновик остаётся при смене варианта')
  const admission = page.waitForResponse(response => response.url().endsWith(`/${first.id}/regenerate`))
  const streaming = page.waitForResponse(response => response.url().includes('/chat/requests/') && response.url().endsWith('/events'))
  await answer.getByRole('button', { name: 'Ответить заново', exact: true }).click()
  const acceptedResponse = await admission, accepted = await acceptedResponse.json()
  expect(acceptedResponse.status()).toBe(202)
  expect(accepted.turn.selected_attempt_id).toBe(first.selected_attempt_id)
  const events = await streaming
  expect(events.url()).toContain(accepted.request.id)
  await events.finished()
  expect(await events.text()).toContain('event: message.completed')
  await expect(answer).toContainText('2 из 2')
  await expect(draft).toHaveValue('Черновик остаётся при смене варианта')
  await expect(row(page, later)).toHaveAttribute('data-message-id', later.selected_attempt.message.id)
  const previous = answer.getByRole('button', { name: 'Предыдущий вариант', exact: true })
  await previous.focus(); await previous.press('Enter')
  await expect(answer).toHaveAttribute('data-message-id', first.selected_attempt.message.id)
  await expect(previous).toBeFocused()
  await answer.getByRole('button', { name: 'Следующий вариант', exact: true }).click()
  await expect(answer).toContainText('2 из 2')
  await expect(page.getByRole('button', { name: 'Отправить', exact: true })).toBeVisible()

  const before = await graph(page, thread.id), path = turnPath(thread.id, first)
  expect(before.turns[0].selected_attempt.model).toBe(first.selected_attempt.model)
  expect(before.turns[0].selected_attempt.message.content).not.toContain('Поздний вопрос Graph')
  const bodies = [regeneration(before, before.turns[0]), regeneration(before, before.turns[0])]
  // Do not start either SSE until BOTH admission responses have arrived.
  const admissions = await Promise.all(bodies.map(body => http(page, `${path}/regenerate`, 'POST', body)))
  expect(admissions.map(result => result.status).sort()).toEqual([202, 409])
  const won = admissions.findIndex(result => result.status === 202), winner = admissions[won].body
  expect(admissions[1 - won].body.error.code).toBe('graph_revision_conflict')
  const pending = await graph(page, thread.id)
  expect(pending.turns[0].selected_attempt_id).toBe(before.turns[0].selected_attempt_id)
  expect(pending.turns[0].latest_attempt.state).toBe('pending')
  expect(pending.active_attempt.request_id).toBe(winner.request.id)
  const replay = await command(page, `${path}/regenerate`, 'POST', bodies[won], 202)
  expect(replay.request.id).toBe(winner.request.id)
  expect((await command(page, `${path}/attempts`)).attempts).toHaveLength(3)

  // Selection commits first while the admitted request is still pending.
  const selectedFirst = await command(page, `${path}/selection`, 'PATCH', selection(pending, first.selected_attempt_id))
  expect(selectedFirst.turn.latest_attempt.state).toBe('pending')
  expect(selectedFirst.turn.selected_attempt_id).toBe(first.selected_attempt_id)
  await complete(page, winner.request.id)
  const completed = await graph(page, thread.id)
  expect(completed.turns[0].selected_attempt_id).toBe(winner.turn.latest_attempt.id)
  expect(completed.revision).toBeGreaterThan(selectedFirst.revision)
  const stale = await http(page, `${path}/selection`, 'PATCH', selection(selectedFirst, first.selected_attempt_id))
  expect(stale.status).toBe(409); expect(stale.body.error.code).toBe('graph_revision_conflict')

  // Completion commits first; a subsequent fresh manual selection wins.
  const last = await command(page, `${path}/regenerate`, 'POST', regeneration(completed, completed.turns[0]), 202)
  await complete(page, last.request.id)
  const completeFirst = await graph(page, thread.id)
  expect(completeFirst.turns[0].selected_attempt_id).toBe(last.turn.latest_attempt.id)
  const selectedLast = await command(page, `${path}/selection`, 'PATCH', selection(completeFirst, first.selected_attempt_id))
  expect(selectedLast.turn.selected_attempt_id).toBe(first.selected_attempt_id)
  expect(selectedLast.revision).toBeGreaterThan(completeFirst.revision)
  const followupRequest = await send(page, thread.id, 'Продолжение выбранной версии', policy.default_model)
  const final = await graph(page, thread.id), variants = await command(page, `${path}/attempts`)
  expect(final.turns).toHaveLength(3)
  expect(final.turns[0].selected_attempt_id).toBe(first.selected_attempt_id)
  expect(final.turns[1].selected_attempt_id).toBe(later.selected_attempt_id)
  expect(final.turns[2].selected_attempt.message.content).toContain('Контекст: Поздний вопрос Graph')
  expect(variants.attempts).toHaveLength(4)
  expect(final.active_attempt).toBeNull(); expect(final.unknown_request_id).toBeNull()
  const physical = await command(page, `threads/${thread.id}`)
  expect(physical.messages).toHaveLength(9)
  const proof = { thread_id: thread.id, title, branch_id: final.active_branch_id, revision: final.revision,
    turns: final.turns.map(turn => ({ id: turn.id, user: turn.user_message.id,
      anchor: turn.assistant_display_sequence, selected: turn.selected_attempt_id })),
    attempts: savedAttempts(variants.attempts), message_ids: physical.messages.map(message => message.id),
    followup_request_id: followupRequest, context_selection_id: first.selected_attempt_id }
  await open(page, title)
  await expect(row(page, first)).toContainText('1 из 4')
  await expect(row(page, first)).toHaveAttribute('data-message-id', first.selected_attempt.message.id)
  await expect(page.locator('.chat-turn-user')).toHaveCount(3)
  await page.screenshot({ path: `${evidence}/graph-before-restart.png`, fullPage: true })
  console.log('CHAT_GRAPH_BEFORE_OK: UI regenerate/select -> two admissions -> both commit orders -> stale CAS -> follow-up')
  return proof
}

export async function graphAfter(page, proof, evidence) {
  isolated(page)
  if (!proof?.thread_id || proof.attempts?.length !== 4) throw new Error('Missing Graph restart proof')
  const restored = await graph(page, proof.thread_id)
  expect(restored.active_branch_id).toBe(proof.branch_id)
  expect(restored.revision).toBe(proof.revision)
  expect(restored.turns.map(turn => ({ id: turn.id, user: turn.user_message.id,
    anchor: turn.assistant_display_sequence, selected: turn.selected_attempt_id }))).toEqual(proof.turns)
  const first = restored.turns[0]
  const variants = await command(page, `${turnPath(proof.thread_id, first)}/attempts`)
  expect(savedAttempts(variants.attempts)).toEqual(proof.attempts)
  const physical = await command(page, `threads/${proof.thread_id}`)
  expect(physical.messages.map(message => message.id)).toEqual(proof.message_ids)
  for (const [name, width, height] of [['desktop', 1440, 900], ['phone', 390, 844]]) {
    await page.setViewportSize({ width, height })
    await open(page, proof.title)
    await expect(row(page, first)).toContainText('1 из 4')
    await expect(row(page, first)).toHaveAttribute('data-message-id', first.selected_attempt.message.id)
    await expect(page.locator('.chat-turn-user')).toHaveCount(3)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/graph-after-restart-${name}.png`, fullPage: true, animations: 'disabled' })
  }
  console.log('CHAT_GRAPH_AFTER_OK: PostgreSQL restart -> exact turns/variants/selection/history -> desktop and phone reload')
}
