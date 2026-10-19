import { expect, type Page } from '@playwright/test'
import type { components } from '../src/shared/api.generated'
import { workspace } from './workspace-fixtures'
import { gate, openGraphThread } from './conversation-graph-fixture'

type Attempt = components['schemas']['GraphAttemptView']
type Turn = components['schemas']['GraphTurnView']
type Branch = components['schemas']['BranchView']
type RecordTurn = Pick<Turn, 'id' | 'turn_sequence' | 'assistant_display_sequence'
  | 'user_message' | 'selected_attempt_id'> & { attempts: Attempt[] }
type Execution = { branch: string; turn: RecordTurn; attempt: Attempt; material?: string; kind?: string }
export const uid = (n: number) => `22222222-2222-4222-8222-${String(n).padStart(12, '0')}`
const clone = <T>(value: T): T => structuredClone(value)
const threadTitle = 'Сохранённые ветки'
export { gate }
export const editor = (page: Page) => page.getByRole('textbox', { name: 'Изменённое сообщение', exact: true })
export const branches = (page: Page) => page.getByRole('combobox', { name: 'Ветка разговора', exact: true })
export const editRow = (page: Page, id: string) => page.locator(`[data-edit-message-id="${id}"]`)
export const openEditThread = (page: Page) => openGraphThread(page, threadTitle)

export async function editFixture(page: Page, count = 3) {
  const app = await workspace(page)
  let serial = 1000
  const id = () => uid(serial++)
  const thread = { id: uid(1), title: threadTitle, created_at: 1, updated_at: 1 }
  function record(sequence: number, text: string): RecordTurn {
    const request = id(), turnId = id()
    const message = { id: id(), request_id: request, sequence: sequence * 2 - 1, content: text,
      role: 'user' as const, state: 'complete' as const, attachments: [], created_at: 1, updated_at: 1 }
    const attempt: Attempt = { id: id(), turn_id: turnId, request_id: request, ordinal: 1,
      model: 'deepseek-flash', state: 'completed', error_code: null, created_at: 1, updated_at: 1,
      message: { ...message, id: id(), role: 'assistant', sequence: sequence * 2, content: `Ответ ${sequence}` } }
    return { id: turnId, turn_sequence: sequence, assistant_display_sequence: sequence * 2,
      user_message: message, selected_attempt_id: attempt.id, attempts: [attempt] }
  }
  const root = { id: thread.id, parent_branch_id: null, fork_from_turn_id: null, branch_ordinal: 1, created_at: 1 }
  const all = new Map<string, { meta: Branch; turns: RecordTurn[] }>([[root.id, { meta: root,
    turns: Array.from({ length: count }, (_, index) => record(index + 1, `Вопрос ${index + 1}`)) }]])
  const requests = new Map<string, Execution>()
  const state = { active: root.id, revision: 1, unknown: null as string | null, graphReads: 0, graphFailures: 0,
    olderReads: 0, events: [] as string[], requestReads: [] as string[], commands: [] as { path: string; body: any }[],
    abort: '', reject: '', graphDelayAt: 0,
    pause: {} as Partial<Record<'edit' | 'regenerate' | 'send' | 'selection' | 'graph' | 'events', ReturnType<typeof gate>>>,
    onGraph: (_before?: number) => {} }
  const active = () => all.get(state.active)!
  const view = (turn: RecordTurn): Turn => {
    const completed = turn.attempts.filter(item => item.state === 'completed')
    const position = completed.findIndex(item => item.id === turn.selected_attempt_id)
    const { attempts, ...base } = turn
    return { ...base, selected_attempt: completed[position] ?? null, latest_attempt: attempts.at(-1) ?? null,
      completed_count: completed.length, selected_completed_position: position < 0 ? null : position + 1,
      previous_completed_attempt_id: completed[position - 1]?.id ?? null,
      next_completed_attempt_id: completed[position + 1]?.id ?? null }
  }
  const requestView = (attempt: Attempt) => ({ id: attempt.request_id, thread_id: thread.id, model: attempt.model,
    state: attempt.state, error_code: attempt.error_code, created_at: 1, updated_at: state.revision })
  const turnView = (turn: RecordTurn) => ({ thread_id: thread.id, active_branch_id: state.active,
    revision: state.revision, turn: view(turn) })
  const graph = (before?: number) => {
    const eligible = active().turns.filter(turn => before === undefined || turn.turn_sequence < before)
    const turns = eligible.slice(-50).map(view)
    return { thread, active_branch_id: state.active, revision: state.revision, turns,
      next_before_turn_sequence: eligible.length > 50 ? turns[0].turn_sequence : null,
      active_attempt: active().turns.flatMap(turn => turn.attempts)
        .find(attempt => ['pending', 'streaming'].includes(attempt.state)) ?? null, unknown_request_id: state.unknown }
  }
  function pending(turn: RecordTurn, requestId: string, regenerate = false) {
    const attempt = regenerate ? clone(turn.attempts.at(-1)!) : turn.attempts[0]
    attempt.id = id(); attempt.message.id = id()
    attempt.request_id = requestId; attempt.message.request_id = requestId
    attempt.state = 'pending'; attempt.message.state = 'partial'; attempt.message.content = ''
    if (regenerate) { attempt.ordinal++; turn.attempts.push(attempt) }
    else { turn.user_message.request_id = requestId; turn.selected_attempt_id = null }
    return attempt
  }
  function finish(requestId: string, outcome: Attempt['state'] = 'completed') {
    const execution = requests.get(requestId)!
    const attempt = execution.attempt
    attempt.state = outcome; attempt.error_code = outcome === 'completed' ? null : 'provider_outcome_unknown'
    attempt.message.state = outcome === 'completed' ? 'complete' : 'interrupted'
    attempt.message.content = `Ответ на: ${execution.turn.user_message.content}`
    if (outcome === 'completed') execution.turn.selected_attempt_id = attempt.id
    else state.unknown = requestId
    state.revision++
  }
  function fork(sourceId: string, text: string, requestId = id(), completed = true) {
    const parent = active(), index = parent.turns.findIndex(turn => turn.id === sourceId)
    const source = parent.turns[index], selected = view(source).selected_attempt ?? source.attempts.at(-1)!
    const meta: Branch = { id: id(), parent_branch_id: state.active, fork_from_turn_id: sourceId,
      branch_ordinal: all.size + 1, created_at: all.size + 1 }
    const edited = record(source.turn_sequence, text), attempt = pending(edited, requestId)
    edited.user_message.attachments = clone(source.user_message.attachments ?? []).map(item => ({ ...item, id: id() }))
    attempt.model = selected.model
    const prefix = clone(parent.turns.slice(0, index))
    all.set(meta.id, { meta, turns: [...prefix, edited] }); state.active = meta.id; state.revision++
    requests.set(requestId, { branch: meta.id, turn: edited, attempt })
    if (completed) finish(requestId)
    return { meta, edited, attempt }
  }
  function switchTo(branch: string) { state.active = branch; state.revision++ }
  for (const turn of active().turns) requests.set(turn.attempts[0].request_id,
    { branch: root.id, turn, attempt: turn.attempts[0] })
  await page.route('**/api/v1/chat/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const json = (value: unknown, status = 200) => route.fulfill({ json: clone(value), status }).catch(() => {})
    const denied = (code: string, status = 409) => json({ error: { code } }, status)
    if (path === '/api/v1/chat/threads') return json({ threads: [thread], next_cursor: null })
    if (path === `/api/v1/chat/threads/${thread.id}`) return json({ thread, graph_version: 1, messages: [], next_before_sequence: null })
    if (path.endsWith('/graph')) {
      state.graphReads++
      const before = Number(url.searchParams.get('before_turn_sequence')) || undefined
      if (before) state.olderReads++
      state.onGraph(before)
      if (state.graphFailures-- > 0) return denied('unavailable', 503)
      if (url.searchParams.has('branch_id') && url.searchParams.get('branch_id') !== state.active)
        return denied('graph_revision_conflict')
      const snapshot = clone(graph(before))
      if (state.graphReads === state.graphDelayAt) await state.pause.graph?.wait
      return json(snapshot)
    }
    if (path.endsWith('/branches')) {
      const before = Number(url.searchParams.get('before_branch_ordinal')) || Infinity
      const eligible = [...all.values()].map(item => item.meta).filter(item => item.branch_ordinal < before)
        .sort((a, b) => b.branch_ordinal - a.branch_ordinal)
      return json({ thread_id: thread.id, active_branch_id: state.active, active_branch: active().meta,
        revision: state.revision, branches: eligible.slice(0, 50),
        next_before_branch_ordinal: eligible.length > 50 ? eligible[49].branch_ordinal : null })
    }
    const turn = active().turns.find(item => path.includes(`/turns/${item.id}/`))
    if (turn && path.endsWith('/attempts')) return json({ ...turnView(turn), attempts: turn.attempts.slice(-20), next_before_ordinal: null })
    if (request.method() === 'POST' || request.method() === 'PATCH') {
      const body = request.postDataJSON()
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      state.commands.push({ path, body })
      const kind = path.endsWith('/edit') ? 'edit' : path.endsWith('/regenerate') ? 'regenerate'
        : path.endsWith('/requests') ? 'send' : 'selection'
      const material = JSON.stringify({ ...body, expected_revision: undefined })
      const old = requests.get(body.request_id)
      let execution: Execution | undefined = old
      if (old?.material && (old.material !== material || old.kind !== kind)) return denied('request_conflict')
      if (!old && (body.branch_id !== state.active || body.expected_revision !== state.revision))
        return denied('graph_revision_conflict')
      if (state.reject) return denied(state.reject, state.reject === 'message_unchanged' ? 422 : 409)
      if (!old && kind !== 'selection' && state.unknown) return denied('provider_outcome_unknown')
      if (kind === 'selection') {
        if (path.endsWith('/branch-selection')) switchTo(body.target_branch_id)
        else if (turn) { turn.selected_attempt_id = body.attempt_id; state.revision++ }
      } else if (!old && kind === 'edit' && turn) {
        fork(turn.id, body.text, body.request_id, false); execution = requests.get(body.request_id)
      } else if (!old && kind === 'regenerate' && turn) {
        const attempt = pending(turn, body.request_id, true)
        state.revision++
        execution = { branch: state.active, turn, attempt }; requests.set(body.request_id, execution)
      } else if (!old && kind === 'send') {
        const next = record((active().turns.at(-1)?.turn_sequence ?? 0) + 1, body.text)
        const attempt = pending(next, body.request_id)
        active().turns.push(next); state.revision++
        execution = { branch: state.active, turn: next, attempt }; requests.set(body.request_id, execution)
      }
      if (execution && !old) { execution.material = material; execution.kind = kind }
      const receipt = kind === 'selection' ? path.endsWith('/branch-selection') ? graph() : turnView(turn!)
        : kind === 'send' ? requestView(execution!.attempt)
        : kind === 'edit' ? { thread_id: thread.id, created_branch: all.get(execution!.branch)!.meta,
          turn_id: execution!.turn.id, request: requestView(execution!.attempt), active_branch_id: state.active, revision: state.revision }
        : { ...turnView(execution!.turn), execution_branch_id: execution!.branch, request: requestView(execution!.attempt) }
      const snapshot = clone(receipt)
      await state.pause[kind]?.wait
      if (state.abort === kind) { state.abort = ''; return route.abort('failed') }
      return json(snapshot, kind === 'selection' ? 200 : 202)
    }
    const execution = [...requests.values()].find(item => path.includes(`/requests/${item.attempt.request_id}`))
    if (execution && path.endsWith('/events')) {
      state.events.push(execution.attempt.request_id)
      await state.pause.events?.wait
      if (['pending', 'streaming'].includes(execution.attempt.state)) finish(execution.attempt.request_id)
      return route.fulfill({ headers: { 'content-type': 'text/event-stream' },
        body: `event: ${execution.attempt.state === 'completed' ? 'message.done' : 'message.interrupted'}\ndata: {}\n\n` }).catch(() => {})
    }
    if (execution) { state.requestReads.push(execution.attempt.request_id); return json(requestView(execution.attempt)) }
    if (path.includes('/requests/')) return denied('request_not_found', 404)
    return route.fallback()
  })
  return { app, state, thread, root, all, active, graph, view, record, requests, fork, finish, switchTo }
}
