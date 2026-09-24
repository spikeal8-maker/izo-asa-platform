import { useEffect, useRef, useState } from 'react'
import type { ChatPolicyView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { CHAT_IMAGE_ACCEPT, chatImageProblem, prepareChatImage } from './chatAttachments'
import './AttachmentControl.css'

export type ChatAttachmentDraft = {
  id: string
  file: File
  url: string
}

export function useChatAttachment({
  policy, selectedVision, visionModel, onModelChange,
}: {
  policy: ChatPolicyView | null
  selectedVision: boolean
  visionModel: { id: string; label: string } | null
  onModelChange: (modelId: string) => void
}) {
  const [attachments, setAttachments] = useState<ChatAttachmentDraft[]>([])
  const [message, setMessage] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const current = useRef<ChatAttachmentDraft[]>([])

  useEffect(() => () => {
    current.current.forEach(item => URL.revokeObjectURL(item.url))
  }, [])

  function replace(next: ChatAttachmentDraft[]) {
    current.current = next
    setAttachments(next)
  }

  async function add(value: File | File[]) {
    if (!policy) return
    const files = Array.isArray(value) ? value : [value]
    if (!files.length) return
    const maximum = policy.max_attachments
    const slots = Math.max(0, maximum - current.current.length)
    if (!slots) {
      setMessage(`Можно прикрепить не больше ${maximum} изображений.`)
      return
    }
    const candidates = files.slice(0, slots)
    try {
      for (const file of candidates) await prepareChatImage(file, policy.max_image_bytes)
    } catch (reason) {
      setMessage(chatImageProblem(reason))
      return
    }
    if (!selectedVision) {
      if (!visionModel) {
        setMessage('Модель не поддерживает изображения.')
        return
      }
      onModelChange(visionModel.id)
    }
    const created = candidates.map(file => ({
      id: crypto.randomUUID(),
      file,
      url: URL.createObjectURL(file),
    }))
    replace([...current.current, ...created])
    if (files.length > slots) {
      setMessage(`Можно прикрепить не больше ${maximum} изображений.`)
    } else if (!selectedVision && visionModel) {
      setMessage(`Для изображения выбрана ${visionModel.label}.`)
    } else {
      setMessage('')
    }
  }

  function remove(id: string) {
    const removed = current.current.find(item => item.id === id)
    if (removed) URL.revokeObjectURL(removed.url)
    replace(current.current.filter(item => item.id !== id))
    setMessage('')
  }

  function clear() {
    current.current.forEach(item => URL.revokeObjectURL(item.url))
    replace([])
    setMessage('')
    if (inputRef.current) inputRef.current.value = ''
  }

  const input = <input ref={inputRef} className="chat-file-input" type="file" multiple
    accept={CHAT_IMAGE_ACCEPT} aria-label="Выбрать изображения"
    onChange={event => {
      const files = Array.from(event.currentTarget.files ?? [])
      event.currentTarget.value = ''
      if (files.length) void add(files)
    }} />

  const preview = attachments.length > 0 && <div className="chat-attachment-strip"
      data-testid="chat-attachment-strip" aria-label="Прикреплённые изображения">
    {attachments.map(item => <div key={item.id} className="chat-attachment-tile"
        data-testid="chat-attachment-preview">
      <img src={item.url} alt="" />
      <span className="chat-attachment-sr">{item.file.name}</span>
      <button type="button" aria-label={`Удалить изображение ${item.file.name}`}
        onClick={() => remove(item.id)}>
        <Icon name="close" />
      </button>
    </div>)}
  </div>

  return { attachments, message, inputRef, input, preview, add, remove, clear }
}
