import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ApiError, type AuthView, type MessageView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import { ChatMessage } from './ChatMessage'
import { chatProblem } from './chatAttachments'
import { editableTurn } from './useConversationGraph'
import { submitBranchEdit, type BranchContext } from './useConversationBranches'

type EditControls = ReturnType<ReturnType<typeof useMessageEdit>['forMessage']>

// RequestCreate uses Python str.strip, not JavaScript trim (notably NEL/C0/BOM).
const boundary = '[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]'
const strip = (text: string) => text.replace(new RegExp(`^${boundary}+|${boundary}+$`, 'g'), '')
export function editTextProblem(original: string, draft: string, attachments: number) {
  if (Array.from(draft).length > 6000) return 'Не больше 6000 символов.'
  if (draft.includes('\0')) return 'Сообщение содержит недопустимый символ.'
  if (!strip(draft) && !attachments) return 'Введите сообщение.'
  return strip(draft) === strip(original) ? 'Сообщение не изменено' : ''
}

type EditOperation = { turnId: string; body: components['schemas']['BranchEdit'] }
export function useMessageEdit(context: BranchContext) {
  const { auth, threadId, graph, selection, selected } = context
  const pending = useRef<EditOperation | null>(null)
  const controller = useRef<AbortController | null>(null)
  const [operation, setOperation] = useState<EditOperation | null>(null)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState('')
  useEffect(() => {
    pending.current = null; setOperation(null); setSaving(false); setFeedback('')
    return () => { controller.current?.abort(); controller.current = null }
  }, [auth?.account.id, threadId])
  async function save(turnId: string, text: string) {
    const current = graph.current.current
    if (!auth || !threadId || !current || context.busy || context.pendingAdmission || controller.current) return false
    let at = selection.current
    if (!selected(threadId, at)) return false
    const turn = editableTurn(current, turnId)
    const source = turn?.selected_attempt ?? turn?.latest_attempt
    if (!pending.current && (!graph.coherent.current || current.active_attempt || current.unknown_request_id
      || !turn
      || editTextProblem(turn.user_message.content, text, turn.user_message.attachments?.length ?? 0))) return false
    const intent = pending.current ?? { turnId, body: { request_id: crypto.randomUUID(),
      branch_id: current.active_branch_id, expected_revision: current.revision, source_attempt_id: source!.id, text } }
    pending.current = intent; setOperation(intent); setSaving(true); setFeedback('')
    const owner = new AbortController(); controller.current = owner
    const valid = () => !owner.signal.aborted && selected(threadId, at)
    try {
      const receipt = await submitBranchEdit(threadId, intent.turnId, intent.body, auth.csrf_token, owner.signal)
      if (!valid()) return false
      pending.current = null; setOperation(null)
      graph.invalidate()
      const reopening = context.reopen()
      at = selection.current
      const loaded = await reopening
      if (!valid()) return true
      const fresh = graph.current.current
      if (loaded && graph.coherent.current && fresh?.active_branch_id === receipt.created_branch.id
        && fresh.active_attempt?.request_id === receipt.request.id && !graph.isTerminal(receipt.request.id))
        { context.start(receipt.request.id); void context.stream(receipt.request.id, threadId) }
      if (!loaded) setFeedback('Сообщение принято. Обновите ветку для продолжения.')
      return true
    } catch (reason) {
      if (!valid()) return false
      if (reason instanceof ApiError && reason.status < 500 && reason.status !== 408) {
        pending.current = null; setOperation(null)
      }
      setFeedback(pending.current ? 'Приём не подтверждён. Проверьте тот же запрос.' : chatProblem(reason))
      if (reason instanceof ApiError && reason.code === 'graph_revision_conflict') {
        graph.invalidate()
        const reopening = context.reopen(); at = selection.current
        await reopening
      }
      return false
    } finally { if (controller.current === owner) { controller.current = null; setSaving(false) } }
  }
  return { saving, pendingAdmission: Boolean(operation), error: feedback,
    check: () => operation ? save(operation.turnId, operation.body.text) : Promise.resolve(false),
    forMessage(id: string) {
      const turn = editableTurn(graph.value, id, true)
      if (!turn) return undefined
      const uncertain = operation?.turnId === turn.id
      return { turn, saving, uncertain, feedback: uncertain || !operation ? feedback : '',
        blocked: context.busy || context.pendingAdmission || Boolean(operation && !uncertain)
          || !uncertain && (!graph.ready || Boolean(graph.value?.unknown_request_id || graph.value?.active_attempt)),
        save: (text: string) => save(turn.id, text) }
    } }
}

export function ChatMessageEdit({ message, auth, control, beforeLayout }: {
  message: MessageView; auth: AuthView | null | undefined
  control?: EditControls; beforeLayout: () => void
}) {
  const [open, setOpen] = useState(false)
  // Keep persisted CRLF until an actual input event.
  const [draft, setDraft] = useState(message.content)
  const trigger = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const root = useRef<HTMLDivElement>(null)
  const returnFocus = useRef(false)
  useLayoutEffect(() => {
    if (open) input.current?.focus({ preventScroll: true })
    else if (returnFocus.current) trigger.current?.focus({ preventScroll: true })
    returnFocus.current = false
  }, [open])
  const problem = editTextProblem(message.content, draft, message.attachments?.length ?? 0)
  const model = control?.turn.selected_attempt?.model ?? control?.turn.latest_attempt?.model
  function changeOpen(value: boolean, restore = true) {
    beforeLayout()
    if (value) setDraft(message.content)
    returnFocus.current = !value && restore
    setOpen(value)
  }
  async function save() {
    if (!control || control.saving || control.blocked || !control.uncertain && problem) return
    let redirected: HTMLElement | null = null
    const moved = (event: FocusEvent) => {
      if (event.target instanceof HTMLElement && !root.current?.contains(event.target)) redirected = event.target
    }
    document.addEventListener('focusin', moved)
    try {
      const accepted = await control.save(draft)
      if (accepted) {
        const form = input.current?.form
        if (root.current) changeOpen(false, false)
        const restore = () => {
          const group = document.querySelector<HTMLElement>('.chat-branch-controls')
          if (!group) return
          if (form?.isConnected || group.getAttribute('aria-busy') === 'true') {
            requestAnimationFrame(restore); return
          }
          if (document.activeElement !== document.body) return
          const target = redirected?.isConnected && !redirected.matches(':disabled') ? redirected
            : group
          target.focus({ preventScroll: true })
        }
        requestAnimationFrame(restore)
      }
    } finally { document.removeEventListener('focusin', moved) }
  }
  return <div ref={root} className="chat-message-edit" data-edit-message-id={message.id}>
    <ChatMessage message={message} auth={auth} />
    {control && <div className="chat-message-actions" style={{ justifyContent: 'flex-end' }}>
      <button ref={trigger} type="button" hidden={open} disabled={control.blocked || control.saving}
        onClick={() => changeOpen(true)}>Изменить</button>
      {open && <form className="full-width" aria-label="Редактирование сообщения" onSubmit={event => { event.preventDefault(); void save() }}
        onKeyDown={event => {
          if (event.key === 'Escape' && !event.nativeEvent.isComposing && !control.saving) {
            event.preventDefault(); event.stopPropagation(); changeOpen(false)
          }
        }}>
        <label>Изменённое сообщение
          <textarea ref={input} value={draft} rows={3} style={{ height: 100, resize: 'none' }} readOnly={control.saving || control.uncertain}
            onChange={event => setDraft(event.target.value)} aria-describedby={`edit-note-${message.id}`} />
        </label>
        <div className="chat-message-actions">
          <button type="submit" disabled={control.blocked || control.saving || !control.uncertain && Boolean(problem)}>
            {control.saving ? 'Сохраняем…' : control.uncertain ? 'Проверить запрос' : 'Сохранить и отправить'}
          </button>
          <button type="button" disabled={control.saving} onClick={() => changeOpen(false)}>Отмена</button>
        </div>
        <small>Модель: {model}. История и вложения сохранятся.</small>
        <div id={`edit-note-${message.id}`} role={control.feedback ? 'alert' : 'status'}>
          {control.feedback || (control.uncertain ? 'Проверка использует тот же запрос.' : problem)}
        </div>
      </form>}
    </div>}
  </div>
}
