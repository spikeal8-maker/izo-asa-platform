import { useCallback, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from 'react'
import { apiRequest, type MessageView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import type { Selection } from './useThreadSelection'

export type GraphAttempt = components['schemas']['GraphAttemptView']
export type GraphTurn = components['schemas']['GraphTurnView']
export type GraphPage = components['schemas']['GraphPage']
export type GraphTurnState = components['schemas']['GraphTurnState']
export type DisplayMessage = MessageView & { graph_turn_id?: string }
const running = (attempt: GraphAttempt | null) => attempt && ['pending', 'streaming'].includes(attempt.state)

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
  const [value, setValue] = useState<GraphPage | null>(null)
  const beforeChange = useRef<() => void>(() => {})
  const epoch = useRef(0)
  const publish = useCallback((next: GraphPage) => {
    const old = current.current
    if (old?.thread.id === next.thread.id && old.turns.some(turn => turn.selected_attempt_id
      && next.turns.some(item => item.id === turn.id && item.selected_attempt_id !== turn.selected_attempt_id)))
      beforeChange.current()
    current.current = next
    setValue(next)
    setMessages(displayMessages(next.turns))
  }, [setMessages])
  const reset = useCallback(() => {
    epoch.current++
    current.current = null; setValue(null)
  }, [])
  const mergePage = useCallback((page: GraphPage, older = false) => {
    const old = current.current
    const same = old?.thread.id === page.thread.id && old.active_branch_id === page.active_branch_id
    if (old?.thread.id === page.thread.id && (page.revision < old.revision
      || !same && page.revision === old.revision)) return false
    const known = new Set(page.turns.map(turn => turn.id))
    const incoming = page.turns.map(turn => witnessedTurn(turn, same ? old.turns.find(item => item.id === turn.id) : undefined))
    const turns = [...(same ? old.turns.filter(turn => !known.has(turn.id)) : []), ...incoming]
      .sort((a, b) => a.turn_sequence - b.turn_sequence)
    const active = witnessed(page.active_attempt, same
      ? old.turns.find(turn => turn.id === page.active_attempt?.turn_id) : undefined)
    publish({ ...page, turns, active_attempt: running(active) ? active : null,
      unknown_request_id: active?.error_code === 'provider_outcome_unknown'
        ? active.request_id : page.unknown_request_id, next_before_turn_sequence: same && !older
      ? old.next_before_turn_sequence : page.next_before_turn_sequence })
    return true
  }, [publish])
  const mergeTurn = useCallback((state: GraphTurnState) => {
    const old = current.current
    if (!old || old.thread.id !== state.thread_id || old.active_branch_id !== state.active_branch_id
      || !Number.isSafeInteger(state.revision) || state.revision < old.revision) return false
    const turn = witnessedTurn(state.turn, old.turns.find(item => item.id === state.turn.id))
    const latest = turn.latest_attempt
    const active = running(latest) ? latest : old.active_attempt?.turn_id === state.turn.id ? null : old.active_attempt
    const previousUnknown = old.turns.find(turn => turn.id === state.turn.id)?.latest_attempt?.request_id
    publish({ ...old, revision: state.revision,
      turns: old.turns.map(item => item.id === turn.id ? turn : item), active_attempt: active,
      unknown_request_id: latest?.error_code === 'provider_outcome_unknown' ? latest.request_id
        : old.unknown_request_id === previousUnknown ? null : old.unknown_request_id })
    return true
  }, [publish])
  const refreshTurn = useCallback(async (threadId: string, turnId: string, signal?: AbortSignal) => {
    const at = selection.current, stamp = epoch.current
    const state = await apiRequest<GraphTurnState>(
      `/api/v1/chat/threads/${threadId}/turns/${turnId}/attempts`, { signal })
    if (!selected(threadId, at) || stamp !== epoch.current) return null
    if (state.thread_id !== threadId || !state.turn || state.turn.id !== turnId
      || !Number.isSafeInteger(state.revision)) throw new Error('Invalid Graph turn')
    mergeTurn(state)
    return state
  }, [mergeTurn, selected, selection])
  const load = useCallback(async (threadId: string, signal?: AbortSignal,
    before?: number, preparePrepend?: () => void) => {
    const at = selection.current, stamp = epoch.current
    const active = current.current?.thread.id === threadId ? current.current.active_attempt : null
    const page = await apiRequest<GraphPage>(`/api/v1/chat/threads/${threadId}/graph`
      + (before === undefined ? '' : `?before_turn_sequence=${before}`), { signal })
    if (!selected(threadId, at) || stamp !== epoch.current) return null
    if (page.thread?.id !== threadId || !Array.isArray(page.turns) || page.turns.length > 50
      || !page.active_branch_id || !Number.isSafeInteger(page.revision)) throw new Error('Invalid Graph page')
    if (before !== undefined && (!current.current || page.revision >= current.current.revision)) preparePrepend?.()
    mergePage(page, before !== undefined)
    if (before === undefined && active && current.current?.turns.some(turn => turn.id === active.turn_id)
      && !page.turns.some(turn => turn.id === active.turn_id)) await refreshTurn(threadId, active.turn_id, signal)
    return current.current
  }, [mergePage, refreshTurn, selected, selection])
  return { value, current, beforeChange, reset, load, mergeTurn, refreshTurn }
}
export type ConversationGraph = ReturnType<typeof useConversationGraph>
