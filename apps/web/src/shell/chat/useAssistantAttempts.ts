import { useEffect, useRef, useState } from 'react'
import { ApiError, apiRequest, type ChatRequestView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import { chatProblem } from './chatAttachments'
import type { GraphTurnState } from './useConversationGraph'
import { useConversationBranches, type BranchContext } from './useConversationBranches'

type Regeneration = { threadId: string; turnId: string; body: components['schemas']['GraphRegenerate'] }
type Accepted = components['schemas']['GraphRequestAccepted']
export type AttemptControls = NonNullable<ReturnType<ReturnType<typeof useAssistantAttempts>['forTurn']>>
const conflict = (reason: unknown) => reason instanceof ApiError && reason.code === 'graph_revision_conflict'
const knownRejection = (reason: unknown) => reason instanceof ApiError && reason.status < 500 && reason.status !== 408

export function useAssistantAttempts(context: BranchContext) {
  const { auth, threadId, busy, graph, selection, selected, start, idle, stream } = context
  const pending = useRef<Regeneration | null>(null)
  const admitting = useRef(false)
  const [pendingView, setPendingView] = useState<Regeneration | null>(null)
  const selecting = useRef<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const controllers = useRef(new Set<AbortController>())
  useEffect(() => {
    pending.current = null; admitting.current = false; setPendingView(null)
    selecting.current = null; setSaving(null); setFeedback({})
    return () => { controllers.current.forEach(controller => controller.abort()); controllers.current.clear() }
  }, [auth?.account.id, threadId])
  const note = (id: string, text: string) => setFeedback(current => ({ ...current, [id]: text }))
  const clearPending = () => { pending.current = null; setPendingView(null) }

  async function regenerate(turnId: string) {
    const current = graph.current.current
    let at = selection.current
    if (!auth || !threadId || !current || !selected(threadId, at) || busy || selecting.current || admitting.current
      || context.pendingAdmission || branches.saving || branches.pendingAdmission) return
    const turn = current.turns.find(item => item.id === turnId)
    if (!pending.current && turn?.selected_attempt?.state !== 'completed') return
    if (pending.current && pending.current.turnId !== turnId) return
    if (!pending.current && (current.unknown_request_id || !graph.coherent.current)) return
    const replay = pending.current
    const operation = replay ?? { threadId, turnId, body: { request_id: crypto.randomUUID(),
      branch_id: current.active_branch_id, source_attempt_id: turn!.selected_attempt!.id,
      expected_revision: current.revision } }
    pending.current = operation; setPendingView(operation); note(turnId, '')
    admitting.current = true
    const controller = new AbortController(); controllers.current.add(controller)
    const valid = () => !controller.signal.aborted && selected(threadId, at)
    start(operation.body.request_id)
    try {
      let request: ChatRequestView | null = null
      let admittedHere = false
      if (replay) {
        try {
          request = await apiRequest<ChatRequestView>(`/api/v1/chat/requests/${operation.body.request_id}`,
            { signal: controller.signal })
        } catch (reason) {
          if (!(reason instanceof ApiError && reason.status === 404)) throw reason
        }
      }
      if (!valid()) return
      if (!request || graph.current.current?.active_branch_id !== operation.body.branch_id) {
        const accepted = await apiRequest<Accepted>(
          `/api/v1/chat/threads/${threadId}/turns/${turnId}/regenerate`, {
            method: 'POST', csrf: auth.csrf_token, data: operation.body, signal: controller.signal,
          })
        if (!valid()) return
        const observed = graph.current.current
        const execution = accepted.execution_branch_id ?? (accepted.active_branch_id === operation.body.branch_id
          && observed?.active_branch_id === operation.body.branch_id ? operation.body.branch_id : null)
        if (accepted.thread_id !== threadId || accepted.turn.id !== turnId
          || accepted.request.id !== operation.body.request_id || accepted.request.thread_id !== threadId
          || execution !== operation.body.branch_id || !Number.isSafeInteger(accepted.revision))
          throw new Error('Invalid regeneration identity')
        request = accepted.request
        if (accepted.active_branch_id === execution && observed?.active_branch_id === execution)
          admittedHere = graph.mergeTurn(accepted) && !replay && !accepted.execution_branch_id
        else graph.invalidate()
      }
      if (request.id !== operation.body.request_id || request.thread_id !== threadId)
        throw new Error('Invalid request identity')
      if (!valid()) return
      clearPending()
      if (!admittedHere) {
        const reloading = branches.retry(); at = selection.current
        if (!await reloading) { idle(); return }
      }
      if (!valid()) return
      if ((admittedHere || graph.coherent.current) && graph.current.current?.active_branch_id === operation.body.branch_id
        && graph.current.current.active_attempt?.request_id === request.id && !graph.isTerminal(request.id))
        await stream(request.id, threadId)
      else idle()
    } catch (reason) {
      if (!valid()) return
      if (knownRejection(reason)) clearPending()
      idle()
      if (conflict(reason)) {
        await graph.load(threadId, controller.signal).catch(() => {})
        if (valid()) note(turnId, 'Выбор уже изменился. Проверьте вариант и повторите.')
      } else note(turnId, pending.current
        ? 'Приём не подтверждён. Проверьте запрос.' : chatProblem(reason))
    } finally { controllers.current.delete(controller); if (!controller.signal.aborted) admitting.current = false }
  }

  async function select(turnId: string, attemptId: string) {
    const current = graph.current.current, at = selection.current
    if (!auth || !threadId || !current || !selected(threadId, at)
      || selecting.current || pending.current || branches.saving || branches.pendingAdmission) return
    const turn = current.turns.find(item => item.id === turnId)
    if (!turn || ![turn.previous_completed_attempt_id, turn.next_completed_attempt_id].includes(attemptId)) return
    selecting.current = turnId; setSaving(turnId); note(turnId, '')
    const controller = new AbortController(); controllers.current.add(controller)
    const valid = () => !controller.signal.aborted && selected(threadId, at)
    try {
      const state = await apiRequest<GraphTurnState>(`/api/v1/chat/threads/${threadId}/turns/${turnId}/selection`, {
        method: 'PATCH', csrf: auth.csrf_token, signal: controller.signal,
        data: { branch_id: current.active_branch_id, attempt_id: attemptId, expected_revision: current.revision },
      })
      if (!valid()) return
      if (state.thread_id !== threadId || state.turn.id !== turnId
        || state.active_branch_id !== current.active_branch_id) throw new Error('Invalid selection response')
      graph.mergeTurn(state)
      await graph.load(threadId, controller.signal)
    } catch (reason) {
      if (!valid()) return
      try {
        const state = await graph.refreshTurn(threadId, turnId, controller.signal)
        await graph.load(threadId, controller.signal)
        if (valid() && conflict(reason)) note(turnId, 'Выбор уже изменился. Показан сохранённый вариант.')
        else if (valid() && state?.turn.selected_attempt_id !== attemptId) note(turnId, chatProblem(reason))
      } catch { if (valid()) note(turnId, 'Выбор не проверен. Восстановите связь и повторите.') }
    } finally {
      controllers.current.delete(controller)
      if (valid()) { selecting.current = null; setSaving(null) }
    }
  }

  const branches = useConversationBranches({ ...context,
    pendingAdmission: context.pendingAdmission || Boolean(pendingView) || Boolean(saving) })
  const pendingAdmission = Boolean(pendingView) || branches.pendingAdmission
  const blocked = busy || context.pendingAdmission || !pendingView && (!graph.ready || Boolean(graph.value?.unknown_request_id))
    || branches.saving || branches.pendingAdmission
  return { branches: { ...branches, pendingAdmission,
      check: () => pending.current ? regenerate(pending.current.turnId) : branches.check() }, pendingAdmission,
    saving: Boolean(saving) || branches.saving,
    navigationBlocked: busy || pendingAdmission || branches.saving,
    executionBlocked: !context.pendingAdmission && Boolean(graph.value && !graph.ready || graph.value?.unknown_request_id),
    forTurn(turnId?: string) {
      const turn = graph.value?.turns.find(item => item.id === turnId)
      if (!turn) return undefined
      const opening = !threadId || !selected(threadId, selection.current)
      return { turn, blocked: blocked || opening || Boolean(saving) || Boolean(pendingView && pendingView.turnId !== turnId),
        saving: opening || Boolean(saving) || Boolean(pendingView), uncertain: pendingView?.turnId === turnId,
        feedback: feedback[turn.id] ?? '', regenerate: () => void regenerate(turn.id),
        select: (attemptId: string) => void select(turn.id, attemptId) }
    } }
}
