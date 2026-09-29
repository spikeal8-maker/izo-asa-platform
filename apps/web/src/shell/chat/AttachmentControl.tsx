import { useLayoutEffect, useRef, useState } from 'react'
import { Icon } from '../../shared/ui/Icon'
import type { ChatDisplayPolicy, ChatModel } from './modelCatalog'
import { CHAT_IMAGE_ACCEPT, chatImageProblem, forgetChatOperations, forgetUnstartedOperations, pendingChatNotice,
  prepareChatImage, reserveChatOperation, type ChatAttachmentDraft } from './chatAttachments'
import { releaseChatMedia } from './useChatPreflight'
import './AttachmentControl.css'

const active = new Map<string, number>()
const leaving = new Set<string>()
export function beginChatMedia(accountId: string) { active.set(accountId, (active.get(accountId) ?? 0) + 1) }
export function endChatMedia(accountId: string) {
  const count = (active.get(accountId) ?? 1) - 1
  if (count) active.set(accountId, count)
  else { active.delete(accountId); if (leaving.delete(accountId)) releaseChatMedia(accountId) }
}
export function leaveChatMedia(accountId?: string) {
  if (!accountId) return
  if (active.has(accountId)) leaving.add(accountId)
  else releaseChatMedia(accountId)
}

export function useChatAttachment({ policy, accountId, selectedVision, visionModel, locked, onModelChange }: {
  policy: ChatDisplayPolicy | null
  accountId?: string
  selectedVision: boolean
  visionModel: ChatModel | null
  locked: boolean
  onModelChange: (model: ChatModel) => void
}) {
  const [attachments, setAttachments] = useState<ChatAttachmentDraft[]>([])
  const [message, setMessage] = useState('')
  const [validating, setValidating] = useState(false)
  const current = useRef<ChatAttachmentDraft[]>([])
  const adding = useRef(false)
  const owner = useRef(accountId)
  const inputRef = useRef<HTMLInputElement>(null)

  function replace(next: ChatAttachmentDraft[]) { current.current = next; setAttachments(next) }
  function clear(consumed?: ChatAttachmentDraft[]) {
    void (consumed?.length ? forgetChatOperations(accountId, consumed)
      : forgetUnstartedOperations(accountId, current.current)).catch(() => {})
    current.current.forEach(item => URL.revokeObjectURL(item.url))
    replace([]); setMessage('')
    if (inputRef.current) inputRef.current.value = ''
  }
  useLayoutEffect(() => {
    owner.current = accountId
    clear()
    setMessage(pendingChatNotice(accountId))
    return () => { owner.current = undefined
      void forgetUnstartedOperations(accountId, current.current).catch(() => {})
      current.current.forEach(item => URL.revokeObjectURL(item.url)); current.current = [] }
  }, [accountId])

  async function add(files: File[]) {
    if (!policy || !accountId || !files.length || locked) return
    const startedFor = owner.current
    if (!startedFor) return
    if (adding.current) { setMessage('Дождитесь проверки изображения.'); return }
    beginChatMedia(accountId)
    adding.current = true; setValidating(true)
    const operations: string[] = []
    try {
      const maximum = policy.max_attachments ?? 0
      if (!maximum) { setMessage('Изображения пока недоступны.'); return }
      const slots = Math.max(0, maximum - current.current.length)
      if (!slots) { setMessage(`Можно прикрепить не больше ${maximum} изображений.`); return }
      const chosen = files.slice(0, slots)
      const prepared = []
      for (const file of chosen) prepared.push(await prepareChatImage(file, policy.max_image_bytes ?? 0))
      if (owner.current !== startedFor) return
      if (!selectedVision) {
        if (!visionModel) { setMessage('Подключите модель, которая принимает изображения.'); return }
        onModelChange(visionModel)
      }
      const used = new Set(current.current.map(item => item.operationId))
      for (const image of prepared) {
        const operationId = await reserveChatOperation(startedFor!, image, used)
        operations.push(operationId); used.add(operationId)
      }
      if (owner.current !== startedFor) {
        await forgetUnstartedOperations(startedFor, operations.map(operationId => ({ operationId })))
        return
      }
      const drafts = chosen.map((file, index) => ({ id: crypto.randomUUID(), operationId: operations[index],
        file, url: URL.createObjectURL(file) }))
      replace([...current.current, ...drafts])
      setMessage(files.length > slots ? `Можно прикрепить не больше ${maximum} изображений.` : '')
    } catch (reason) {
      await forgetUnstartedOperations(startedFor, operations.map(operationId => ({ operationId }))).catch(() => {})
      if (owner.current === startedFor) setMessage(chatImageProblem(reason))
    } finally { adding.current = false; setValidating(false); endChatMedia(accountId) }
  }

  function remove(id: string) {
    if (locked) return
    const item = current.current.find(value => value.id === id)
    if (item) {
      void forgetUnstartedOperations(accountId, [item]).catch(() => {})
      URL.revokeObjectURL(item.url)
    }
    replace(current.current.filter(value => value.id !== id)); setMessage('')
  }

  const input = <input ref={inputRef} className="chat-file-input" type="file" multiple tabIndex={-1}
    accept={CHAT_IMAGE_ACCEPT} aria-label="Выбрать изображения" disabled={locked}
    onChange={event => { const files = Array.from(event.currentTarget.files ?? [])
      event.currentTarget.value = ''; void add(files) }} />
  const preview = attachments.length > 0 && <div className="chat-attachment-strip"
    data-testid="chat-attachment-strip" aria-label="Прикреплённые изображения">
    {attachments.map(item => <div key={item.id} className="chat-attachment-tile"
      data-testid="chat-attachment-preview">
      <img src={item.url} alt="" />
      <span className="chat-attachment-sr">{item.file.name}</span>
      <button type="button" aria-label={`Удалить изображение ${item.file.name}`} disabled={locked}
        onClick={event => { const form = event.currentTarget.form; remove(item.id)
          requestAnimationFrame(() => form?.querySelector<HTMLButtonElement>('.chat-composer-plus')?.focus()) }}>
        <Icon name="close" /></button>
    </div>)}
  </div>
  return { attachments, message, validating, inputRef, input, preview, add, clear }
}
