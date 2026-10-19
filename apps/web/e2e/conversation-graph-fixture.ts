import { expect, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const uuid = (value: number) => `11111111-1111-4111-8111-${String(value).padStart(12, '0')}`
export const gate = () => {
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  return { wait, release }
}
const clone = <T>(value: T): T => structuredClone(value)
const message = (id: number, sequence: number, content: string, role = 'assistant') => ({
  id: uuid(id), request_id: uuid(id + 100000), sequence, content, role,
  state: 'complete', attachments: [], created_at: 1, updated_at: 1,
})
const attempt = (turn: number, ordinal: number) => ({
  id: uuid(20000 + turn * 100 + ordinal), turn_id: uuid(10000 + turn),
  request_id: uuid(40000 + turn * 100 + ordinal), ordinal, model: 'deepseek-flash',
  state: 'completed', error_code: null as string | null,
  message: { ...message(60000 + turn * 100 + ordinal, ordinal === 1 ? turn * 2 : 1000 + ordinal,
    `**Ответ ${turn}, вариант ${ordinal}**\n\nСохранённый текст ответа.`), request_id: uuid(40000 + turn * 100 + ordinal) },
  created_at: 1, updated_at: 1,
})
export async function openGraphThread(page: Page, title = 'Разговор с вариантами') {
  const opener = page.getByRole('button', { name: 'Открыть панель', exact: true })
  if (await opener.isVisible()) await opener.click()
  await page.getByRole('button', { name: title, exact: true }).click()
}
export const answer = (page: Page, sequence = 1) => page.locator(`[data-turn-id="${uuid(10000 + sequence)}"]`)
export const regenerateButton = (page: Page) => answer(page).getByRole('button', { name: 'Ответить заново', exact: true })
export const previousButton = (page: Page) => answer(page).getByRole('button', { name: 'Предыдущий вариант', exact: true })
export const nextButton = (page: Page) => answer(page).getByRole('button', { name: 'Следующий вариант', exact: true })

export async function graphFixture(page: Page, count = 2) {
  await workspace(page)
  const thread = { id: uuid(1), title: 'Разговор с вариантами', created_at: 1, updated_at: 1 }
  const other = { ...thread, id: uuid(2), title: 'Другой разговор' }
  const branch = uuid(3)
  const records = Array.from({ length: count }, (_, index) => {
    const sequence = index + 1, first = attempt(sequence, 1)
    return { id: uuid(10000 + sequence), turn_sequence: sequence,
      assistant_display_sequence: sequence * 2,
      user_message: message(80000 + sequence, sequence * 2 - 1, `Вопрос ${sequence}`, 'user'),
      selected_attempt_id: first.id as string | null, attempts: [first] }
  })
  const state = {
    thread, other, branch, records, revision: 1, graphReads: 0, olderReads: 0,
    commands: [] as { method: string; body: Record<string, any>; path: string }[], events: 0,
    graphGate: null as ReturnType<typeof gate> | null,
    graphDelayAt: 0, eventGate: null as ReturnType<typeof gate> | null,
    selectionGate: null as ReturnType<typeof gate> | null,
    abortAdmission: false, abortSelection: false, rejectRegenerate: '', outcome: 'completed',
    terminalRevision: true, requestReads: 0,
  }
  const turn = (record: typeof records[number]) => {
    const completed = record.attempts.filter(item => item.state === 'completed')
    const position = completed.findIndex(item => item.id === record.selected_attempt_id)
    return { id: record.id, turn_sequence: record.turn_sequence,
      assistant_display_sequence: record.assistant_display_sequence, user_message: record.user_message,
      selected_attempt_id: record.selected_attempt_id,
      selected_attempt: completed[position] ?? null, latest_attempt: record.attempts.at(-1) ?? null,
      completed_count: completed.length, selected_completed_position: position < 0 ? null : position + 1,
      previous_completed_attempt_id: completed[position - 1]?.id ?? null,
      next_completed_attempt_id: completed[position + 1]?.id ?? null }
  }
  const turnState = (record: typeof records[number]) => ({
    thread_id: thread.id, active_branch_id: branch, revision: state.revision, turn: turn(record),
  })
  const requestView = (current: ReturnType<typeof attempt>) => ({
    id: current.request_id, thread_id: thread.id, state: current.state,
    error_code: current.error_code, model: current.model, created_at: 1, updated_at: state.revision,
  })
  const graph = (before?: number) => {
    const eligible = records.filter(item => !before || item.turn_sequence < before)
    const turns = eligible.slice(-50).map(turn)
    const attempts = records.flatMap(item => item.attempts)
    return { thread, active_branch_id: branch, revision: state.revision, turns,
      next_before_turn_sequence: eligible.length > 50 ? turns[0].turn_sequence : null,
      active_attempt: attempts.find(item => ['pending', 'streaming'].includes(item.state)) ?? null,
      unknown_request_id: attempts.find(item => item.error_code === 'provider_outcome_unknown')?.request_id ?? null }
  }
  await page.route('**/api/v1/chat/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const json = (value: unknown, status = 200) => route.fulfill({ json: clone(value), status }).catch(() => {})
    const denied = (code: string) => json({ error: { code } }, 409)
    if (path === '/api/v1/chat/threads') return json({ threads: [thread, other], next_cursor: null })
    if (path === `/api/v1/chat/threads/${other.id}`) return json({
      thread: other, messages: [message(90000, 1, 'Сообщение другого чата', 'user')], next_before_sequence: null,
    })
    if (path === `/api/v1/chat/threads/${thread.id}`) return json({
      thread, graph_version: 1, messages: records.flatMap(item => [item.user_message,
        ...item.attempts.map(value => value.message)]), next_before_sequence: null,
    })
    if (path.endsWith(`/${thread.id}/graph`)) {
      state.graphReads++
      const before = Number(url.searchParams.get('before_turn_sequence')) || undefined
      if (before) state.olderReads++
      const snapshot = clone(graph(before))
      if (state.graphReads === state.graphDelayAt) await state.graphGate?.wait
      return json(snapshot)
    }
    const record = records.find(item => path.includes(`/turns/${item.id}/`))
    if (record && path.endsWith('/attempts')) return json({ ...turnState(record),
      attempts: record.attempts.slice(-20), next_before_ordinal: record.attempts.length > 20
        ? record.attempts.at(-20)!.ordinal : null })
    if (record && ['POST', 'PATCH'].includes(request.method())) {
      const body = request.postDataJSON()
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      expect(request.headers()['x-izo-request']).toBe('web')
      state.commands.push({ method: request.method(), body, path })
      if (path.endsWith('/regenerate')) {
        const replay = record.attempts.find(item => item.request_id === body.request_id)
        if (replay) return json({ ...turnState(record), request: requestView(replay) }, 202)
        if (state.rejectRegenerate) return denied(state.rejectRegenerate)
        if (body.expected_revision !== state.revision) return denied('graph_revision_conflict')
        expect(body.branch_id).toBe(branch)
        expect(body.source_attempt_id).toBe(record.selected_attempt_id)
        const next = attempt(record.turn_sequence, record.attempts.length + 1)
        next.request_id = body.request_id; next.message.request_id = body.request_id
        next.state = 'pending'; next.message.state = 'partial'; next.message.content = ''
        record.attempts.push(next); state.revision++
        if (state.abortAdmission) { state.abortAdmission = false; return route.abort('failed') }
        return json({ ...turnState(record), request: requestView(next) }, 202)
      }
      if (path.endsWith('/selection')) {
        if (body.expected_revision !== state.revision) return denied('graph_revision_conflict')
        expect(body.branch_id).toBe(branch)
        expect(record.attempts.some(item => item.id === body.attempt_id && item.state === 'completed')).toBe(true)
        record.selected_attempt_id = body.attempt_id; state.revision++
        const snapshot = clone(turnState(record))
        if (state.abortSelection) { state.abortSelection = false; return route.abort('failed') }
        await state.selectionGate?.wait
        return json(snapshot)
      }
    }
    const current = records.flatMap(item => item.attempts).find(item => path.includes(`/requests/${item.request_id}`))
    if (current && path.endsWith('/events')) {
      state.events++; current.state = 'streaming'
      await state.eventGate?.wait
      if (current.state !== 'stopped') {
        current.state = state.outcome
        current.error_code = state.outcome === 'interrupted' ? 'provider_outcome_unknown' : null
        current.message.state = state.outcome === 'completed' ? 'complete' : state.outcome
        current.message.content = `**Ответ ${records.find(item => item.id === current.turn_id)!.turn_sequence}, вариант ${current.ordinal}**\n\nНовый сохранённый текст.`
        if (state.outcome === 'completed') records.find(item => item.id === current.turn_id)!.selected_attempt_id = current.id
        if (current.state === 'completed' || state.terminalRevision) state.revision++
      }
      return route.fulfill({ headers: { 'content-type': 'text/event-stream' },
        body: `event: ${current.state === 'completed' ? 'message.completed' : 'message.interrupted'}\ndata: ${JSON.stringify({ code: current.error_code })}\n\n` }).catch(() => {})
    }
    if (current && path.endsWith('/stop')) {
      current.state = 'stopped'; current.message.state = 'stopped'; state.revision++
      state.eventGate?.release()
      return json(requestView(current))
    }
    if (current) { state.requestReads++; return json(requestView(current)) }
    if (path.includes('/requests/')) return json({ error: { code: 'request_not_found' } }, 404)
    return route.fallback()
  })
  return { ...state, state, graph, turnState, addVariant(sequence = 1) {
    const record = records[sequence - 1]
    record.attempts.push(attempt(sequence, record.attempts.length + 1))
    state.revision++
  } }
}
