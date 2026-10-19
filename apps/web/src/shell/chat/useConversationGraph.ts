import { useCallback, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from 'react'
import { apiRequest, type MessageView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import type { Selection } from './useThreadSelection'
import { readBranchPages } from './useConversationBranches'

export type GraphAttempt = components['schemas']['GraphAttemptView']
export type GraphTurn = components['schemas']['GraphTurnView']
export type GraphPage = components['schemas']['GraphPage']
export type GraphTurnState = components['schemas']['GraphTurnState']
export type DisplayMessage = MessageView & { graph_turn_id?: string }
const running = (attempt: GraphAttempt | null) => attempt && ['pending', 'streaming'].includes(attempt.state)
export function editableTurn(page: GraphPage | null, id: string, byMessage = false) {
  const turn = page?.turns.find(item => (byMessage ? item.user_message.id : item.id) === id)
  const source = turn?.selected_attempt ?? turn?.latest_attempt
  return source && !running(source) ? turn : undefined
}

// Request lifecycle can finish without advancing the branch revision (for example,
// credential disable). A late snapshot must not resume an observed terminal request.
function witnessed(attempt: GraphAttempt | null, old?: GraphTurn): GraphAttempt | null {
  if (!attempt || !old) return attempt
  const previous = [old.selected_attempt, old.latest_attempt].find(item =>
    item?.id === attempt.id && item.request_id === attempt.request_id)
  return previous && (!running(previous) && running(attempt)
    || previous.state === 'completed' && attempt.state !== 'completed') ? previous : attempt
}
function witnessedTurn(turn: GraphTurn, old?: GraphTurn): GraphTurn {
  return { ...turn, selected_attempt: witnessed(turn.selected_attempt, old),
    latest_attempt: witnessed(turn.latest_attempt, old) }
}

function displayMessages(turns: GraphTurn[]): DisplayMessage[] {
  return turns.flatMap(turn => {
    const attempt = turn.selected_attempt ?? turn.latest_attempt
    return [turn.user_message, ...(attempt ? [{ ...attempt.message,
      sequence: turn.assistant_display_sequence, graph_turn_id: turn.id }] : [])]
  })
}

export function useConversationGraph(selection: RefObject<Selection>,
  selected: (threadId: string, at: Selection) => boolean,
  setMessages: Dispatch<SetStateAction<MessageView[]>>) {
  const current = useRef<GraphPage | null>(null)
  const observed = useRef(new Map<string, GraphTurn>())
  const lastActive = useRef<GraphAttempt | null>(null)
  const [value, setValue] = useState<GraphPage | null>(null)
  const [ready, setReady] = useState(false)
  const coherent = useRef(false)
  const cache = useRef(new Map<string, GraphPage>())
  const reads = useRef(0)
  const beforeChange = useRef<() => void>(() => {})
  const epoch = useRef(0)
  const publish = useCallback((next: GraphPage) => {
    const old = current.current
    if (old?.thread.id !== next.thread.id || old.active_branch_id !== next.active_branch_id) {
      epoch.current++
      observed.current.clear(); lastActive.current = null
    }
    next.turns.forEach(turn => observed.current.set(turn.id, turn))
    if (next.active_attempt) lastActive.current = next.active_attempt
    const recent = lastActive.current
    const latest = recent && observed.current.get(recent.turn_id)?.latest_attempt
    if (latest?.request_id === recent?.request_id) lastActive.current = latest ?? null
    if (old?.thread.id === next.thread.id && (old.active_branch_id !== next.active_branch_id
      || old.turns.some(turn => turn.selected_attempt_id
        && next.turns.some(item => item.id === turn.id && item.selected_attempt_id !== turn.selected_attempt_id))))
      beforeChange.current()
    current.current = next
    cache.current.set(`${next.thread.id}:${next.active_branch_id}`, next)
    setValue(next)
    setMessages(displayMessages(next.turns))
  }, [setMessages])
  const invalidate = useCallback(() => {
    epoch.current++; reads.current++; coherent.current = false; setReady(false)
  }, [])
  const reset = useCallback(() => {
    invalidate(); cache.current.clear()
    observed.current.clear(); lastActive.current = null
    current.current = null; setValue(null)
  }, [invalidate])
  const mergePage = useCallback((page: GraphPage) => {
    const old = current.current
    const same = old?.thread.id === page.thread.id && old.active_branch_id === page.active_branch_id
    if (old?.thread.id === page.thread.id && (page.revision < old.revision
      || !same && page.revision === old.revision)) return false
    const incoming = page.turns.map(turn => witnessedTurn(turn, same ? observed.current.get(turn.id) : undefined))
    const active = witnessed(page.active_attempt, same
      ? observed.current.get(page.active_attempt?.turn_id ?? '') : undefined)
    publish({ ...page, turns: incoming, active_attempt: running(active) ? active : null,
      // The paid-submission marker also exists during a resumable live stream.
      unknown_request_id: !running(active) && active?.error_code === 'provider_outcome_unknown'
        ? active.request_id : page.unknown_request_id })
    return true
  }, [publish])
  const mergeTurn = useCallback((state: GraphTurnState) => {
    const old = current.current
    if (!old || old.thread.id !== state.thread_id || old.active_branch_id !== state.active_branch_id
      || !Number.isSafeInteger(state.revision) || state.revision < old.revision) return false
    const previous = observed.current.get(state.turn.id)
    const turn = witnessedTurn(state.turn, previous)
    observed.current.set(turn.id, turn)
    const latest = turn.latest_attempt
    const active = running(latest) ? latest : old.active_attempt?.turn_id === state.turn.id ? null : old.active_attempt
    if (state.revision !== old.revision) { coherent.current = false; setReady(false) }
    publish({ ...old, revision: state.revision,
      turns: old.turns.map(item => item.id === turn.id ? turn : item), active_attempt: active,
      unknown_request_id: !running(latest) && latest?.error_code === 'provider_outcome_unknown' ? latest.request_id
        : old.unknown_request_id })
    return true
  }, [publish])
  const refreshTurn = useCallback(async (threadId: string, turnId: string, signal?: AbortSignal) => {
    const at = selection.current, stamp = epoch.current
    const branch = current.current?.active_branch_id
    const state = await apiRequest<GraphTurnState>(
      `/api/v1/chat/threads/${threadId}/turns/${turnId}/attempts${branch ? `?branch_id=${branch}` : ''}`, { signal })
    if (!selected(threadId, at) || stamp !== epoch.current) return null
    if (state.thread_id !== threadId || !state.turn || state.turn.id !== turnId
      || !Number.isSafeInteger(state.revision)) throw new Error('Invalid Graph turn')
    mergeTurn(state)
    return state
  }, [mergeTurn, selected, selection])
  const load = useCallback(async (threadId: string, signal?: AbortSignal,
    before?: number, preparePrepend?: () => void) => {
    const at = selection.current, stamp = epoch.current
    const ticket = ++reads.current, wasCoherent = coherent.current
    coherent.current = false; setReady(false)
    const valid = () => selected(threadId, at) && stamp === epoch.current && (before !== undefined || ticket === reads.current)
    const active = current.current?.thread.id === threadId ? current.current.active_attempt ?? lastActive.current : null
    let page = await readBranchPages(cache.current, current.current, threadId, signal, valid, before, wasCoherent)
    if (!valid()) return null
    // Preserve off-page lifecycle evidence before publishing.
    const recent = active ?? (current.current?.thread.id === threadId ? lastActive.current : null)
    if (before === undefined && page.active_branch_id === current.current?.active_branch_id && recent && running(recent)
      && !page.turns.some(turn => turn.id === recent.turn_id)) {
      await refreshTurn(threadId, recent.turn_id, signal)
      if (!valid()) return null
    }
    const stale = () => {
      const retained = cache.current.get(`${threadId}:${page.active_branch_id}`)
      const ids = new Set(page.turns.map(turn => turn.id))
      return retained && (retained.revision > page.revision || retained.turns.some(turn => !ids.has(turn.id)))
    }
    for (let retry = 0; stale() && retry < 3; retry++) {
      page = await readBranchPages(cache.current, current.current, threadId, signal, valid, before)
      if (!valid()) return null
    }
    if (stale()) throw new Error('Incomplete Graph history')
    if (before !== undefined && (!current.current || page.revision >= current.current.revision)) preparePrepend?.()
    const accepted = mergePage(page)
    coherent.current = accepted; setReady(accepted)
    if (!accepted) throw new Error('Выбор изменился. Обновите ветку перед отправкой.')
    return current.current
  }, [mergePage, refreshTurn, selected, selection])
  const isTerminal = useCallback((requestId: string) => current.current?.unknown_request_id === requestId
    || [...observed.current.values()].some(turn => [turn.selected_attempt, turn.latest_attempt]
      .some(attempt => attempt?.request_id === requestId && !running(attempt))), [])
  return { value, current, ready, coherent, invalidate, beforeChange, reset, load, mergeTurn, refreshTurn, isTerminal }
}
export type ConversationGraph = ReturnType<typeof useConversationGraph>
