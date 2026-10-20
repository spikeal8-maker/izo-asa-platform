import { useEffect, useRef, useState, type RefObject } from 'react'
import { apiRequest, type AuthView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import { chatProblem } from './chatAttachments'
import { useMessageEdit } from './ChatMessageEdit'
import type { ConversationGraph, GraphPage } from './useConversationGraph'
import type { Selection } from './useThreadSelection'

type BranchPage = components['schemas']['BranchPage']
export type BranchFence = { branch_id: string; expected_revision: number }
export type PendingChatRequest = { id: string; threadId: string; payload: string; fence?: BranchFence }
export function nextChatRequest(previous: PendingChatRequest | null, threadId: string,
  text: string, model: string, attachmentIds: string[], graph: GraphPage | null): PendingChatRequest | null {
  const fence = previous ? previous.fence : graph ? { branch_id: graph.active_branch_id, expected_revision: graph.revision } : undefined
  const payload = JSON.stringify([text, model, attachmentIds, fence?.branch_id ?? null])
  if (previous && (previous.threadId !== threadId || previous.payload !== payload)) return null
  return previous ?? { id: crypto.randomUUID(), threadId, payload, fence }
}

export async function submitBranchEdit(threadId: string, turnId: string,
  body: components['schemas']['BranchEdit'], csrf: string, signal: AbortSignal) {
  const receipt = await apiRequest<components['schemas']['BranchEditView']>(
    `/api/v1/chat/threads/${threadId}/turns/${turnId}/edit`, { method: 'POST', csrf, signal, data: body })
  if (receipt.thread_id !== threadId || receipt.request.thread_id !== threadId
    || receipt.request.id !== body.request_id || !receipt.created_branch.id
    || receipt.created_branch.parent_branch_id !== body.branch_id || receipt.created_branch.fork_from_turn_id !== turnId
    || !Number.isSafeInteger(receipt.revision)) throw new Error('Invalid Edit')
  return receipt
}

// Revalidate all retained ranges at one revision before publishing.
export async function readBranchPages(cache: Map<string, GraphPage>, prior: GraphPage | null,
  threadId: string, signal: AbortSignal | undefined, valid: () => boolean, before?: number, fresh = false) {
  async function read(cursor?: number, branch?: string) {
    if (!valid()) throw new DOMException('Selection changed', 'AbortError')
    const query = new URLSearchParams()
    if (cursor !== undefined) query.set('before_turn_sequence', String(cursor))
    if (branch) query.set('branch_id', branch)
    const page = await apiRequest<GraphPage>(`/api/v1/chat/threads/${threadId}/graph${query.size ? `?${query}` : ''}`, { signal })
    if (page.thread?.id !== threadId || !page.active_branch_id || !Number.isSafeInteger(page.revision)
      || !Array.isArray(page.turns) || page.turns.length > 50
      || page.unknown_request_id !== null && typeof page.unknown_request_id !== 'string'
      || branch && page.active_branch_id !== branch) throw new Error('Invalid Graph page')
    return page
  }
  const older = before === undefined ? null : await read(before, prior?.active_branch_id)
  if (older && prior?.thread.id === threadId && fresh && older.revision === prior.revision
    && older.active_branch_id === prior.active_branch_id)
    return { ...older, turns: [...older.turns, ...prior.turns] }
  for (let retry = 0; retry < 3; retry++) {
    const head = await read()
    const retained = cache.get(`${threadId}:${head.active_branch_id}`)
    const previous = retained ?? (prior?.thread.id === threadId ? prior : null)
    const minimum = Math.min(...[...(previous?.turns ?? []), ...(older?.turns ?? [])]
      .map(turn => turn.turn_sequence))
    let page = head, turns = [...head.turns], coherent = true
    const cursors = new Set<number>()
    while (page.next_before_turn_sequence !== null && (turns[0]?.turn_sequence ?? Infinity) > minimum) {
      const cursor = page.next_before_turn_sequence
      if (cursors.has(cursor)) throw new Error('Invalid Graph cursor')
      cursors.add(cursor)
      page = await read(cursor, head.active_branch_id)
      if (page.revision !== head.revision) { coherent = false; break }
      turns = [...page.turns, ...turns]
    }
    if (!coherent) continue
    const ids = new Set(turns.map(turn => turn.id))
    if (ids.size !== turns.length || retained?.turns.some(turn => !ids.has(turn.id)))
      throw new Error('Incomplete Graph history')
    return { ...head, turns, next_before_turn_sequence: page.next_before_turn_sequence }
  }
  throw new Error('Выбор меняется. Обновите ветку.')
}

export type BranchContext = {
  auth: AuthView | null | undefined; threadId: string | null; busy: boolean; pendingAdmission: boolean
  graph: ConversationGraph; selection: RefObject<Selection>
  selected: (threadId: string, at: Selection) => boolean
  reopen: () => Promise<boolean>; start: (id: string) => void; idle: () => void
  stream: (id: string, threadId: string) => Promise<void>
}

export function useConversationBranches(context: BranchContext) {
  const { auth, threadId, graph, selection, selected } = context
  const [value, setValue] = useState<BranchPage | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const locked = useRef(false)
  const recovery = useRef(0)
  const reads = useRef(0)
  const controllers = useRef(new Set<AbortController>())
  const [needsReload, setNeedsReload] = useState(false)
  useEffect(() => {
    setValue(null); setError(''); setSaving(false); setLoading(false); setNeedsReload(false)
    locked.current = false; reads.current++; recovery.current++
    return () => { controllers.current.forEach(item => item.abort()); controllers.current.clear() }
  }, [auth?.account.id, threadId])
  async function load(older = false) {
    if (!threadId || !graph.current.current) return
    const at = selection.current, serial = ++reads.current
    const controller = new AbortController(); controllers.current.add(controller)
    const valid = () => !controller.signal.aborted && selected(threadId, at) && serial === reads.current
    setLoading(true)
    try {
      const cursor = older ? value?.next_before_branch_ordinal : null
      const page = await apiRequest<BranchPage>(`/api/v1/chat/threads/${threadId}/branches`
        + (cursor ? `?before_branch_ordinal=${cursor}` : ''), { signal: controller.signal })
      if (!valid() || page.revision < (graph.current.current?.revision ?? 0)) return
      if (page.thread_id !== threadId || page.branches.length > 50 || page.active_branch.id !== page.active_branch_id)
        throw new Error('Invalid branch page')
      setValue(previous => {
        const merged = new Map((previous?.branches ?? []).map(branch => [branch.id, branch]))
        page.branches.forEach(branch => merged.set(branch.id, branch))
        merged.set(page.active_branch.id, page.active_branch)
        return { ...page, branches: [...merged.values()].sort((a, b) => a.branch_ordinal - b.branch_ordinal),
          next_before_branch_ordinal: !older && previous ? previous.next_before_branch_ordinal : page.next_before_branch_ordinal }
      })
      setError('')
    } catch (reason) { if (valid()) setError(chatProblem(reason)) }
    finally { controllers.current.delete(controller); if (valid()) setLoading(false) }
  }
  useEffect(() => { void load() }, [auth?.account.id, threadId, graph.value?.active_branch_id, graph.value?.revision])
  async function recover() {
    if (!threadId) return false
    const serial = ++recovery.current
    const ok = await context.reopen()
    if (serial !== recovery.current) return false
    setNeedsReload(!ok)
    if (ok) { setError(''); void load() }
    return ok
  }
  const edits = useMessageEdit({ ...context, reopen: recover })
  async function select(target: string) {
    const current = graph.current.current, at = selection.current
    if (!auth || !threadId || !current || !graph.coherent.current || locked.current || context.busy
      || context.pendingAdmission || edits.pendingAdmission || current.active_attempt) return
    locked.current = true; setSaving(true); setError(''); setNeedsReload(true)
    graph.invalidate()
    const controller = new AbortController(); controllers.current.add(controller)
    try {
      await apiRequest<GraphPage>(`/api/v1/chat/threads/${threadId}/branch-selection`, {
        method: 'PATCH', csrf: auth.csrf_token, signal: controller.signal,
        data: { branch_id: current.active_branch_id, target_branch_id: target, expected_revision: current.revision },
      })
      if (selected(threadId, at) && !controller.signal.aborted) await recover()
    } catch (reason) {
      if (selected(threadId, at) && !controller.signal.aborted) {
        await recover()
        if (!controller.signal.aborted) setError(chatProblem(reason))
      }
    } finally {
      controllers.current.delete(controller)
      if (!controller.signal.aborted) { locked.current = false; setSaving(false) }
    }
  }
  return { value, activeId: graph.value?.active_branch_id, loading,
    listed: value?.branches.some(item => item.id === graph.value?.active_branch_id),
    saving: saving || edits.saving, needsReload, error: error || edits.error,
    pendingAdmission: edits.pendingAdmission, forMessage: edits.forMessage, check: edits.check,
    blocked: context.busy || context.pendingAdmission || edits.pendingAdmission || saving || !graph.ready
      || Boolean(graph.value?.active_attempt),
    select, loadMore: () => load(true), retry: recover }
}
