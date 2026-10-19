import { useId, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { ApiError } from '../../shared/api'
import './ThreadRenameForm.css'

export function useThreadRenameEditor(hidden: boolean, pendingId: string | null,
  fallback: RefObject<HTMLButtonElement | null>) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const historyList = useRef<HTMLDivElement>(null)
  const origin = useRef<{ button: HTMLButtonElement; scroll: number } | null>(null)
  const returnFocus = useRef(false)

  useLayoutEffect(() => {
    if (hidden) {
      origin.current = null
      returnFocus.current = false
      setEditingId(null)
      return
    }
    if (editingId) return
    const source = origin.current
    const target = source?.button.isConnected ? source.button : fallback.current
    const active = document.activeElement
    const restore = returnFocus.current && source && target?.isConnected
      && (active === document.body || active === target)
    // Both the editor removal and PATCH unlock must be committed before focusing.
    if (restore && pendingId && target === source.button) return
    origin.current = null
    returnFocus.current = false
    if (!restore || !target || target.disabled) return
    if (historyList.current) historyList.current.scrollTop = source.scroll
    target.focus({ preventScroll: true })
  }, [editingId, hidden, pendingId, fallback])

  function openRename(id: string, button: HTMLButtonElement) {
    returnFocus.current = false
    origin.current = { button, scroll: historyList.current?.scrollTop ?? 0 }
    setEditingId(id)
  }
  function closeRename(restoreFocus: boolean) {
    returnFocus.current = restoreFocus
    if (!restoreFocus) origin.current = null
    setEditingId(null)
  }
  return { editingId, historyList, openRename, closeRename }
}

function renameProblem(reason: unknown) {
  if (reason instanceof ApiError) {
    if (reason.status === 401) return 'Войдите в аккаунт, чтобы сохранить название.'
    if (reason.status === 404) return 'Этот чат недоступен. Название не изменено.'
    if (reason.status === 422) return 'Введите название от 1 до 120 символов без недопустимых знаков.'
    if (reason.status === 403) return 'Не удалось подтвердить доступ. Обновите страницу и повторите.'
  }
  return 'Не удалось сохранить название. Проверьте соединение и повторите.'
}

export function ThreadRenameForm({ title, onSave, onClose }: {
  title: string
  onSave: (title: string) => Promise<boolean>
  onClose: (restoreFocus: boolean) => void
}) {
  const [draft, setDraft] = useState(title)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const saving = useRef(false)
  const mounted = useRef(true)
  const input = useRef<HTMLInputElement>(null)
  const form = useRef<HTMLFormElement>(null)
  const id = useId()
  const normalized = draft.trim()
  const length = Array.from(normalized).length
  const valid = length <= 120 && !/^[\s\u001c-\u001f\u0085]*$/u.test(normalized)
    && !/[\u0000\uD800-\uDFFF]/u.test(normalized)
  useLayoutEffect(() => {
    mounted.current = true
    input.current?.focus({ preventScroll: true })
    input.current?.select()
    return () => { mounted.current = false }
  }, [])
  async function save() {
    if (!valid || saving.current) return
    saving.current = true
    setPending(true); setError('')
    try {
      const saved = await onSave(normalized)
      if (mounted.current && saved) onClose(Boolean(form.current?.contains(document.activeElement)))
    } catch (reason) {
      if (mounted.current) setError(renameProblem(reason))
    } finally {
      saving.current = false
      if (mounted.current) setPending(false)
    }
  }
  return <form ref={form} className="chat-thread-rename" aria-label="Переименование чата"
    onSubmit={event => { event.preventDefault(); void save() }}
    onKeyDown={event => {
      if (event.key !== 'Escape') return
      event.preventDefault(); event.stopPropagation()
      if (!saving.current) onClose(true)
    }}>
    <label htmlFor={id}>Название чата</label>
    <input ref={input} id={id} value={draft} readOnly={pending} autoComplete="off"
      aria-invalid={!valid || undefined} aria-describedby={`${id}-hint`}
      onChange={event => { setDraft(event.target.value); setError('') }} />
    <span id={`${id}-hint`} className="chat-thread-rename-hint">{length}/120 символов</span>
    {error && <span className="chat-thread-rename-error" role="alert">{error}</span>}
    <div className="chat-thread-rename-actions">
      <button className="primary" type="submit" disabled={!valid} aria-disabled={pending || undefined}>
        {pending ? 'Сохраняем…' : 'Сохранить'}</button>
      <button type="button" disabled={pending} onClick={() => onClose(true)}>Отмена</button>
    </div>
  </form>
}
