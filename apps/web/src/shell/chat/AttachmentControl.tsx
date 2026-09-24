import { useEffect, useRef, useState } from 'react'
import type { ChatPolicyView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { CHAT_IMAGE_ACCEPT, chatImageProblem, prepareChatImage } from './chatAttachments'
import './AttachmentControl.css'

export function useChatAttachment({
  policy, selectedVision, visionModel, onModelChange,
}: {
  policy: ChatPolicyView | null
  selectedVision: boolean
  visionModel: { id: string; label: string } | null
  onModelChange: (modelId: string) => void
}) {
  const [attachment, setAttachment] = useState<File | null>(null)
  const [attachmentUrl, setAttachmentUrl] = useState('')
  const [message, setMessage] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!attachment) { setAttachmentUrl(''); return }
    const url = URL.createObjectURL(attachment)
    setAttachmentUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [attachment])

  async function add(file: File) {
    if (!policy) return
    if (attachment) {
      setMessage('В этом Chat пока можно прикрепить одно изображение.')
      return
    }
    setMessage('')
    try {
      await prepareChatImage(file, policy.max_image_bytes)
    } catch (reason) {
      setAttachment(null)
      if (inputRef.current) inputRef.current.value = ''
      setMessage(chatImageProblem(reason))
      return
    }
    if (!selectedVision) {
      if (!visionModel) {
        setMessage('Модель не поддерживает изображения.')
        return
      }
      onModelChange(visionModel.id)
      setMessage(`Для изображения выбрана ${visionModel.label}.`)
    }
    setAttachment(file)
  }

  function remove() {
    setAttachment(null)
    setMessage('')
    if (inputRef.current) inputRef.current.value = ''
  }

  const input = <input ref={inputRef} className="chat-file-input" type="file"
    accept={CHAT_IMAGE_ACCEPT} aria-label="Выбрать изображение"
    onChange={event => {
      const file = event.currentTarget.files?.[0]
      if (file) void add(file)
    }} />

  const preview = attachment && <div className="chat-attachment-preview" data-testid="chat-attachment-preview">
    {attachmentUrl && <img src={attachmentUrl} alt="Прикреплённое изображение" />}
    <span title={attachment.name}>{attachment.name}</span>
    <button type="button" aria-label="Удалить вложение" onClick={remove}>
      <Icon name="close" />
    </button>
  </div>

  return { attachment, message, inputRef, input, preview, add, remove }
}
