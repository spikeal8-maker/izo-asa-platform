// UI/HTTP against the isolated PostgreSQL stack; provider execution is test-only.
import { randomUUID } from 'node:crypto'
import { expect } from '@playwright/test'
export const button = (scope, name) => scope.getByRole('button', { name, exact: true })

function isolated(page) {
  if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_CHAT_ACCEPTANCE !== 'isolated'
    || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(page.url()).hostname))
    throw new Error('Message Edit requires the isolated loopback stack')
}
export async function command(page, path, method = 'GET', data, status = 200) {
  const result = await page.evaluate(async ({ path, method, data }) => {
    const headers = { 'Content-Type': 'application/json', 'X-IZO-Request': 'web' }
    if (method !== 'GET') {
      const auth = await fetch('/api/v1/auth/me', { credentials: 'same-origin', cache: 'no-store' })
      if (!auth.ok) throw new Error('Edit acceptance authentication failed')
      headers['X-CSRF-Token'] = (await auth.json()).csrf_token
    }
    const response = await fetch(`/api/v1/chat/${path}`, { method, headers, cache: 'no-store',
      credentials: 'same-origin', signal: AbortSignal.timeout(15000),
      body: data === undefined ? undefined : JSON.stringify(data) })
    return { status: response.status, body: await response.json() }
  }, { path, method, data })
  expect(result.status, `${method} ${path}`).toBe(status)
  return result.body
}
const graph = (page, threadId) => command(page, `threads/${threadId}/graph`)
export const terminal = (page, id) => expect.poll(async () =>
  (await command(page, `requests/${id}`)).state).toBe('completed')
const user = (page, turn) => page.locator(`[data-edit-message-id="${turn.user_message.id}"]`)
const answer = (page, turn) => page.locator(`[data-turn-id="${turn.id}"]`)
const branchSelector = page => page.getByRole('combobox', { name: 'Ветка разговора', exact: true })
const composer = page => page.getByRole('textbox', { name: 'Сообщение', exact: true })
const draftText = 'Черновик сохраняется при смене ветки'
const evidencePath = (page, folder, name) => `${folder}/edit-${name}-${new URL(page.url()).port || '80'}`
export function contextCases(proof) {
  return proof.edits.map(({ receipt, expected_context_ids }) => ({
    request_id: receipt.request.id, branch_id: receipt.created_branch.id, turn_id: receipt.turn_id,
    revision: receipt.revision, kind: 'edit', ids: expected_context_ids,
  })).concat(proof.followup).map(item => ({ ...item, thread_id: proof.thread_id,
    expected: item.ids.map(id => proof.physical_messages.find(message => message.id === id)) }))
}
export async function complete(page, requestId) {
  const result = await page.evaluate(async id => {
    const response = await fetch(`/api/v1/chat/requests/${id}/events`, {
      credentials: 'same-origin', signal: AbortSignal.timeout(15000), headers: { Accept: 'text/event-stream' },
    })
    return { status: response.status, body: await response.text() }
  }, requestId)
  expect(result.status).toBe(200); expect(result.body).toContain('event: message.done')
  expect((await command(page, `requests/${requestId}`)).state).toBe('completed')
}
async function open(page, title) {
  await page.reload()
  const opener = button(page, 'Открыть панель')
  await expect(composer(page)).toBeVisible()
  if (await opener.isVisible()) await opener.click()
  await button(page, title).click()
}
async function select(page, branchId) {
  const selector = branchSelector(page)
  await expect(selector).toBeEnabled()
  await selector.selectOption(branchId)
  await expect(selector).toHaveValue(branchId)
  await expect(selector).toBeEnabled()
}
async function edit(page, threadId, snapshot, text, viewport, folder) {
  const [prefix, source] = snapshot.turns
  await page.setViewportSize(viewport)
  const draft = composer(page)
  await draft.fill(draftText)
  await page.evaluate(prefixId => {
    window.editLiveNodes = { composer: document.querySelector('.chat-composer-dock textarea'),
      prefix: document.querySelector(`[data-edit-message-id="${prefixId}"]`) }
  }, prefix.user_message.id)
  await button(user(page, source), 'Изменить').click()
  const input = page.getByRole('textbox', { name: 'Изменённое сообщение', exact: true })
  await expect(input).toHaveValue(source.user_message.content)
  await input.fill(text)
  const admitted = page.waitForResponse(response => response.url().endsWith(`/${source.id}/edit`))
  const streamed = page.waitForResponse(response => response.url().includes('/chat/requests/') && response.url().endsWith('/events'))
  await button(page, 'Сохранить и отправить').click()
  const response = await admitted, receipt = await response.json(), material = response.request().postDataJSON()
  expect(response.status()).toBe(202)
  expect(material).toMatchObject({ branch_id: snapshot.active_branch_id,
    source_attempt_id: source.selected_attempt_id, expected_revision: snapshot.revision, text })
  expect(receipt.created_branch).toMatchObject({ parent_branch_id: snapshot.active_branch_id, fork_from_turn_id: source.id })
  expect(receipt.request).toMatchObject({ id: material.request_id, model: source.selected_attempt.model })
  const stream = await streamed
  expect(stream.url()).toContain(receipt.request.id); expect(stream.status()).toBe(200)
  expect(stream.headers()['content-type']).toContain('text/event-stream')
  await expect(page.locator('.chat-assistant-message').last()).toContainText(`Ответ DeepSeek test: ${text}`)
  await terminal(page, receipt.request.id)
  await expect(branchSelector(page)).toBeEnabled()
  await expect(draft).toHaveValue(draftText)
  expect(await page.evaluate(prefixId => window.editLiveNodes.composer === document.querySelector('.chat-composer-dock textarea')
    && window.editLiveNodes.prefix === document.querySelector(`[data-edit-message-id="${prefixId}"]`), prefix.user_message.id)).toBe(true)
  const child = await graph(page, threadId), edited = child.turns[1]
  expect(child.active_branch_id).toBe(receipt.created_branch.id)
  expect(child.turns).toHaveLength(2)
  expect(child.turns[0]).toEqual(prefix)
  expect(edited.id).toBe(receipt.turn_id); expect(edited.id).not.toBe(source.id)
  expect(edited.user_message.id).not.toBe(source.user_message.id)
  expect(edited.user_message.content).toBe(text)
  expect(edited.user_message.attachments).toEqual(source.user_message.attachments)
  expect(edited.selected_attempt.model).toBe(source.selected_attempt.model)
  expect(child.active_attempt).toBeNull(); expect(child.unknown_request_id).toBeNull()
  await expect(page.locator('.chat-turn-user')).toHaveCount(2)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `${evidencePath(page, folder, `before-${viewport.width}`)}.png`, fullPage: true, animations: 'disabled' })
  return { source_turn_id: source.id, body: material, receipt, turns: child.turns,
    expected_context_ids: [prefix.user_message.id, prefix.selected_attempt.message.id, edited.user_message.id] }
}

export async function editBefore(page, folder) {
  isolated(page)
  const title = 'Сохранённые ветки после редактирования', policy = await command(page, 'policy')
  const thread = await command(page, 'threads', 'POST', { title }, 201)
  for (const text of ['Выбранный контекст Edit', 'Исходное сообщение Edit', 'Исходное продолжение Edit']) {
    const current = await graph(page, thread.id)
    const request = await command(page, `threads/${thread.id}/requests`, 'POST', {
      request_id: randomUUID(), text, model: policy.default_model, attachment_ids: [],
      branch_id: current.active_branch_id, expected_revision: current.revision,
    }, 202)
    await complete(page, request.id)
  }
  const initial = await graph(page, thread.id), prefix = initial.turns[0]
  const variant = await command(page, `threads/${thread.id}/turns/${prefix.id}/regenerate`, 'POST', {
    request_id: randomUUID(), branch_id: initial.active_branch_id,
    source_attempt_id: prefix.selected_attempt_id, expected_revision: initial.revision,
  }, 202)
  await complete(page, variant.request.id)
  const root = await graph(page, thread.id), original = await command(page, `threads/${thread.id}`)
  expect(root.turns[0].selected_attempt_id).not.toBe(prefix.selected_attempt_id)
  await page.setViewportSize({ width: 1440, height: 900 }); await open(page, title)
  const desktop = await edit(page, thread.id, root, 'Изменено на компьютере', { width: 1440, height: 900 }, folder)
  await select(page, root.active_branch_id)
  expect((await graph(page, thread.id)).turns).toEqual(root.turns)
  const replay = await command(page, `threads/${thread.id}/turns/${desktop.source_turn_id}/edit`, 'POST', desktop.body, 202)
  expect(replay.created_branch).toEqual(desktop.receipt.created_branch)
  expect(replay.turn_id).toBe(desktop.receipt.turn_id)
  expect(replay.request.id).toBe(desktop.receipt.request.id)
  expect(replay.active_branch_id).toBe(root.active_branch_id)
  expect((await graph(page, thread.id)).active_branch_id).toBe(root.active_branch_id)
  await button(answer(page, prefix), 'Предыдущий вариант').click()
  await expect(answer(page, prefix)).toHaveAttribute('data-message-id', prefix.selected_attempt.message.id)
  const restoredRoot = await graph(page, thread.id)
  expect(restoredRoot.turns[0].selected_attempt_id).toBe(prefix.selected_attempt_id)
  const phone = await edit(page, thread.id, restoredRoot, 'Изменено на телефоне', { width: 390, height: 844 }, folder)
  const branches = await command(page, `threads/${thread.id}/branches`), final = await graph(page, thread.id)
  expect(branches.branches).toHaveLength(3); expect(branches.next_before_branch_ordinal).toBeNull()
  const physical = await command(page, `threads/${thread.id}`)
  for (const message of original.messages)
    expect(physical.messages.find(item => item.id === message.id)).toEqual(message)
  const proof = { thread_id: thread.id, title, active_branch_id: final.active_branch_id, revision: final.revision,
    branches: branches.branches, physical_messages: physical.messages, edits: [desktop, phone],
    projections: { [root.active_branch_id]: restoredRoot.turns,
      [desktop.receipt.created_branch.id]: desktop.turns, [phone.receipt.created_branch.id]: phone.turns } }
  console.log('CHAT_EDIT_BEFORE_OK: desktop/phone branches, immutable history, local selections, UUID replay')
  return proof
}

export async function editAfter(page, proof, folder) {
  isolated(page)
  if (!proof?.thread_id || proof.edits?.length !== 2) throw new Error('Missing Message Edit restart proof')
  const restored = await graph(page, proof.thread_id)
  expect(restored.active_branch_id).toBe(proof.active_branch_id)
  expect(restored.revision).toBe(proof.revision)
  expect((await command(page, `threads/${proof.thread_id}/branches`)).branches).toEqual(proof.branches)
  expect((await command(page, `threads/${proof.thread_id}`)).messages).toEqual(proof.physical_messages)
  for (const edit of proof.edits) expect(await command(page, `requests/${edit.receipt.request.id}`))
    .toMatchObject({ id: edit.receipt.request.id, model: edit.receipt.request.model, state: 'completed' })
  for (const [name, width, height] of [['desktop', 1440, 900], ['phone', 390, 844]]) {
    await page.setViewportSize({ width, height }); await open(page, proof.title)
    for (const [branchId, turns] of Object.entries(proof.projections)) {
      await select(page, branchId)
      expect((await graph(page, proof.thread_id)).turns).toEqual(turns)
      await expect(page.locator('.chat-turn-user')).toHaveCount(turns.length)
      for (const turn of turns) {
        await expect(user(page, turn)).toContainText(turn.user_message.content)
        await expect(answer(page, turn)).toHaveAttribute('data-message-id', turn.selected_attempt.message.id)
      }
    }
    await select(page, proof.active_branch_id)
    await open(page, proof.title)
    await expect(branchSelector(page)).toHaveValue(proof.active_branch_id)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `${evidencePath(page, folder, `after-${name}`)}.png`, fullPage: true, animations: 'disabled' })
  }
  console.log('CHAT_EDIT_AFTER_OK: durable branches/messages/versions, desktop/phone switching and reload')
}
