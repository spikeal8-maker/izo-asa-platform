import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import type { MessageView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import { ChatMessage } from './ChatMessage'
import { chatProblem } from './chatAttachments'
import { editableTurn } from './useConversationGraph'
import { submitBranchEdit, type BranchContext } from './useConversationBranches'
import { useChatScroll } from './useChatScroll'
import { conflict, knownRejection } from './useChatPreflight'

export function useConversationLayout(owner: string | undefined, thread: string | null,
  messages: MessageView[], blocked: boolean, saving: boolean, focused: RefObject<HTMLElement | null>,
  redirect: (event: PointerEvent) => void) {
  const [layout, render] = useState(0)
  const scroll = useChatScroll(owner, thread, [...messages])
  const viewport = useRef<number | null>(null)
  const beforeLayout = () => { scroll.preparePrepend(); render(value => value + 1) }
  useLayoutEffect(() => {
    focused.current = null; viewport.current = null
    document.addEventListener('pointerdown', redirect, true)
    return () => document.removeEventListener('pointerdown', redirect, true)
  }, [owner, thread, redirect])
  useLayoutEffect(() => {
    const node = scroll.scrollRef.current
    const top = node?.getBoundingClientRect().top ?? null
    const delta = top === null ? 0 : top - (viewport.current ?? top)
    if (node && Math.abs(delta) > 0.5 && node.scrollHeight - node.clientHeight - node.scrollTop > 48) {
      node.scrollTop += delta; beforeLayout()
    }
    viewport.current = top
  })
  useLayoutEffect(() => {
    let target = focused.current
    if (saving || !target || document.activeElement !== document.body) return
    if (!target.isConnected) target = document.querySelector<HTMLElement>('.chat-branch-controls')
    else if (blocked) return
    if (target && !target.matches(':disabled')) target.focus({ preventScroll: true })
  }, [blocked, saving, layout])
  return { ...scroll, beforeLayout }
}

// RequestCreate uses Python str.strip, not JavaScript trim (notably NEL/C0/BOM).
const boundary = '[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]'
const strip = (text: string) => text.replace(new RegExp(`^${boundary}+|${boundary}+$`, 'g'), '')
export function editTextProblem(original: string, draft: string, attachments: number) {
  if (Array.from(draft).length > 6000) return 'Не больше 6000 символов.'
  if (draft.includes('\0')) return 'Сообщение содержит недопустимый символ.'
  if (!strip(draft) && !attachments) return 'Введите сообщение.'
  return strip(draft) === strip(original) ? 'Сообщение не изменено' : ''
}

export function useMessageEdit(context: BranchContext) {
  const { auth, threadId, graph, selection, selected } = context
  const pending = useRef<{ turnId: string; body: components['schemas']['BranchEdit'] } | null>(null)
  const controller = useRef<AbortController | null>(null)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState('')
  const operation = pending.current
  useEffect(() => {
    pending.current = null; setSaving(false); setFeedback('')
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
    pending.current = intent; setSaving(true); setFeedback('')
    const owner = new AbortController(); controller.current = owner
    const valid = () => !owner.signal.aborted && selected(threadId, at)
    const reread = () => {
      graph.invalidate()
      const loading = context.reopen(); at = selection.current
      return loading
    }
    try {
      const receipt = await submitBranchEdit(threadId, intent.turnId, intent.body, auth.csrf_token, owner.signal)
      if (!valid()) return false
      pending.current = null
      const loaded = await reread()
      if (!valid()) return true
      const fresh = graph.current.current
      if (loaded && graph.coherent.current && fresh?.active_branch_id === receipt.created_branch.id
        && fresh.active_attempt?.request_id === receipt.request.id && !graph.isTerminal(receipt.request.id))
        { context.start(receipt.request.id); void context.stream(receipt.request.id, threadId) }
      if (!loaded) setFeedback('Сообщение принято. Обновите ветку для продолжения.')
      return true
    } catch (reason) {
      if (!valid()) return false
      if (knownRejection(reason)) pending.current = null
      setFeedback(pending.current ? 'Приём не подтверждён. Проверьте тот же запрос.' : chatProblem(reason))
      if (conflict(reason)) await reread()
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
  message: MessageView; auth: BranchContext['auth']
  control?: ReturnType<ReturnType<typeof useMessageEdit>['forMessage']>; beforeLayout: () => void
}) {
  // null closes the editor without requesting trigger focus.
  const [open, setOpen] = useState<boolean | null>(null)
  // Keep persisted CRLF until an actual input event.
  const [draft, setDraft] = useState(message.content)
  const trigger = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    if (open !== null) (open ? input.current : trigger.current)?.focus({ preventScroll: true })
  }, [open])
  const problem = editTextProblem(message.content, draft, message.attachments?.length ?? 0)
  const { turn, saving, blocked, uncertain, feedback } = control ?? {}
  const model = turn?.selected_attempt?.model ?? turn?.latest_attempt?.model
  const canSave = !saving && !blocked && (uncertain || !problem)
  function changeOpen(value: boolean | null) {
    beforeLayout()
    if (value) setDraft(message.content)
    setOpen(value)
  }
  async function save() {
    if (!control || !canSave) return
    if (await control.save(draft) && input.current) changeOpen(null)
  }
  return <div className="chat-message-edit" data-edit-message-id={message.id}>
    <ChatMessage message={message} auth={auth} />
    {control && <div className="chat-message-actions" style={{ justifyContent: 'flex-end' }}>
      <button ref={trigger} type="button" hidden={open === true} disabled={blocked || saving}
        onClick={() => changeOpen(true)}>Изменить</button>
      {open && <form className="full-width" aria-label="Редактирование сообщения" onSubmit={event => { event.preventDefault(); void save() }}
        onKeyDown={event => {
          if (event.key === 'Escape' && !event.nativeEvent.isComposing && !saving) {
            event.preventDefault(); event.stopPropagation(); changeOpen(false)
          }
        }}>
        <label>Изменённое сообщение
          <textarea ref={input} value={draft} rows={3} style={{ height: 100, resize: 'none' }} readOnly={saving || uncertain}
            onChange={event => setDraft(event.target.value)} aria-describedby={`edit-note-${message.id}`} />
        </label>
        <div className="chat-message-actions">
          <button type="submit" disabled={!canSave}>
            {saving ? 'Сохраняем…' : uncertain ? 'Проверить запрос' : 'Сохранить и отправить'}
          </button>
          <button type="button" disabled={saving} onClick={() => changeOpen(false)}>Отмена</button>
        </div>
        <small>Модель: {model}. История и вложения сохранятся.</small>
        <div id={`edit-note-${message.id}`} role={feedback ? 'alert' : 'status'}>
          {feedback || (uncertain ? 'Проверка использует тот же запрос.' : problem)}
        </div>
      </form>}
    </div>}
  </div>
}
