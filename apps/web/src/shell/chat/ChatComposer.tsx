import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChatPolicyView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { textModels, toolById, tools, type Tool } from './modelCatalog'
import { CHAT_IMAGE_ACCEPT, chatImageProblem, prepareChatImage } from './chatAttachments'
import { menuKeyboard, useComposerLayout } from './composerLayout'
import { useVoiceCapture } from './useVoiceCapture'
import './ChatComposer.css'

export function ChatComposer({
  policy, busy, stoppable, disabled, selectedModelId,
  onModelChange, onSend, onStop, onUnsupported,
}: {
  policy: ChatPolicyView | null
  busy: boolean
  stoppable: boolean
  disabled: boolean
  selectedModelId: string | null
  onModelChange: (modelId: string) => void
  onSend: (text: string, modelId: string, attachment: File | null) => Promise<boolean>
  onStop: () => void
  onUnsupported: () => void
}) {
  const [draft, setDraft] = useState('')
  const [toolsOpen, setToolsOpen] = useState(false)
  const [modelOpen, setModelOpen] = useState(false)
  const [tool, setTool] = useState<Tool | null>(null)
  const [attachment, setAttachment] = useState<File | null>(null)
  const [attachmentUrl, setAttachmentUrl] = useState('')
  const [attachmentMessage, setAttachmentMessage] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const plusButton = useRef<HTMLButtonElement>(null)
  const modelButton = useRef<HTMLButtonElement>(null)
  const voice = useVoiceCapture()
  const forcedExpanded = voice.active || Boolean(tool) || Boolean(attachment)
  const layout = useComposerLayout(draft, forcedExpanded)
  const models = textModels(policy)
  const selectedModel = models.find(item => item.id === selectedModelId)
    ?? models.find(item => item.id === policy?.default_model)
    ?? models[0]
    ?? null

  useEffect(() => {
    if (!attachment) { setAttachmentUrl(''); return }
    const url = URL.createObjectURL(attachment)
    setAttachmentUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [attachment])

  useEffect(() => {
    const dismiss = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (modelOpen && !target.closest('.chat-model-selector,.chat-model-menu')) setModelOpen(false)
      if (toolsOpen && !target.closest('.chat-tools-menu,button[aria-label="Добавить"]')) setToolsOpen(false)
    }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [modelOpen, toolsOpen])

  useEffect(() => {
    if (!modelOpen && !toolsOpen) return
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      if (modelOpen) {
        setModelOpen(false)
        requestAnimationFrame(() => modelButton.current?.focus())
      }
      if (toolsOpen) {
        setToolsOpen(false)
        requestAnimationFrame(() => plusButton.current?.focus())
      }
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [modelOpen, toolsOpen])

  async function attachImage(file: File) {
    if (!policy) return
    if (attachment) {
      setAttachmentMessage('В этом Chat пока можно прикрепить одно изображение.')
      return
    }
    setAttachmentMessage('')
    try {
      await prepareChatImage(file, policy.max_image_bytes)
    } catch (reason) {
      setAttachment(null)
      if (fileInput.current) fileInput.current.value = ''
      setAttachmentMessage(chatImageProblem(reason))
      return
    }
    const current = selectedModel
    if (current && !current.vision) {
      const vision = models.find(item => item.vision)
      if (!vision) {
        setAttachmentMessage('Модель не поддерживает изображения.')
        return
      }
      onModelChange(vision.id)
      setAttachmentMessage(`Для изображения выбрана ${vision.label}.`)
    }
    setTool(null)
    setAttachment(file)
  }

  function removeAttachment() {
    setAttachment(null)
    setAttachmentMessage('')
    if (fileInput.current) fileInput.current.value = ''
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || voice.active || busy || disabled || !selectedModel) return
    if (tool) {
      onUnsupported()
      return
    }
    if (attachment && !selectedModel.vision) {
      setAttachmentMessage('Модель не поддерживает изображения.')
      return
    }
    if (!await onSend(text, selectedModel.id, attachment)) return
    setDraft('')
    removeAttachment()
    requestAnimationFrame(() => layout.textareaRef.current?.focus())
  }

  function selectTool(next: Tool) {
    setTool(next)
    setToolsOpen(false)
    setModelOpen(false)
  }

  function selectModel(modelId: string) {
    const next = models.find(item => item.id === modelId)
    if (!next) return
    if (attachment && !next.vision) {
      setAttachmentMessage('Модель не поддерживает изображения.')
      return
    }
    onModelChange(next.id)
    setAttachmentMessage('')
    setModelOpen(false)
    requestAnimationFrame(() => modelButton.current?.focus())
  }

  return <div className="chat-composer-wrap">
    <form ref={layout.formRef}
      className={`chat-composer ${layout.expanded ? 'is-expanded' : 'is-compact'} ${voice.active ? 'voice-active' : ''}`}
      data-layout={layout.expanded ? 'expanded' : 'compact'}
      onSubmit={event => void submit(event)}
      onPaste={event => {
        const file = Array.from(event.clipboardData.files).find(item => item.type.startsWith('image/'))
        if (!file) return
        event.preventDefault()
        void attachImage(file)
      }}
      onDragOver={event => {
        if (Array.from(event.dataTransfer.types).includes('Files')) event.preventDefault()
      }}
      onDrop={event => {
        if (!event.dataTransfer.files.length) return
        event.preventDefault()
        const file = Array.from(event.dataTransfer.files).find(item => item.type.startsWith('image/'))
          ?? event.dataTransfer.files[0]
        void attachImage(file)
      }}
      onKeyDown={event => {
        if (event.key !== 'Escape') return
        if (modelOpen) {
          event.preventDefault(); setModelOpen(false)
          requestAnimationFrame(() => modelButton.current?.focus())
        }
        if (toolsOpen) {
          event.preventDefault(); setToolsOpen(false)
          requestAnimationFrame(() => plusButton.current?.focus())
        }
      }}>
      <div ref={layout.measureRef} className="chat-composer-measure" aria-hidden="true" />
      {voice.active
        ? <div className="chat-voice-capture" role="status" aria-label="Микрофон активен">
            <span className="chat-voice-label">Слушаю</span>
            <div ref={voice.waveformRef} className="chat-voice-waveform" aria-hidden="true">
              {Array.from({ length: voice.barCount }, (_, index) =>
                <span key={index} style={{ transform: 'scaleY(0.08)' }} />)}
            </div>
          </div>
        : <textarea ref={layout.textareaRef} rows={1} value={draft} aria-label="Сообщение"
            placeholder={disabled ? 'Подключите ключ DeepSeek' : 'Спросите что-нибудь'}
            disabled={disabled || busy}
            onChange={event => setDraft(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }} />}
      <input ref={fileInput} className="chat-file-input" type="file"
        accept={CHAT_IMAGE_ACCEPT} aria-label="Выбрать изображение"
        onChange={event => {
          const file = event.currentTarget.files?.[0]
          if (file) void attachImage(file)
        }} />
      <button ref={plusButton} type="button" className="chat-circle-button chat-composer-plus"
        data-composer-control="compact" aria-label="Добавить" aria-expanded={toolsOpen}
        disabled={busy}
        onClick={() => { setToolsOpen(value => !value); setModelOpen(false) }}>
        <Icon name="plus" />
      </button>
      {(tool || attachment) && <div className="chat-composer-state">
        {tool && <button type="button" className="chat-state-chip selected"
          aria-label={`Убрать инструмент: ${toolById[tool].label}`}
          onClick={() => setTool(null)}>
          <Icon name={toolById[tool].icon} /><span>{toolById[tool].label}</span><Icon name="close" />
        </button>}
        {attachment && <div className="chat-attachment-preview" data-testid="chat-attachment-preview">
          {attachmentUrl && <img src={attachmentUrl} alt="Прикреплённое изображение" />}
          <span title={attachment.name}>{attachment.name}</span>
          <button type="button" aria-label="Удалить вложение" onClick={removeAttachment}>
            <Icon name="close" />
          </button>
        </div>}
      </div>}
      <button ref={modelButton} type="button" className="chat-model-selector"
        data-composer-control="compact" aria-label="Выбрать модель" aria-expanded={modelOpen}
        disabled={busy || !selectedModel}
        onClick={() => { setModelOpen(value => !value); setToolsOpen(false) }}>
        <span>{selectedModel?.label ?? 'Модель'}</span><Icon name="chevron" />
      </button>
      <button type="button" className={`chat-circle-button chat-mic-button ${voice.active ? 'active' : ''}`}
        data-composer-control="compact" aria-label={voice.active ? 'Остановить микрофон' : 'Микрофон'}
        disabled={busy} onClick={() => voice.active ? voice.stop() : void voice.start()}>
        <Icon name="mic" />
      </button>
      {busy
        ? <button type="button" className="chat-send-button" data-composer-control="compact"
            aria-label="Остановить ответ" disabled={!stoppable} onClick={onStop}><Icon name="close" /></button>
        : <button type="submit" className="chat-send-button" data-composer-control="compact"
            aria-label="Отправить" disabled={disabled || !draft.trim() || voice.active}>
            <Icon name="send" />
          </button>}
      {voice.error && <div className="chat-voice-error" role="alert">{voice.error}</div>}
      {attachmentMessage && <div className="chat-attachment-note" role="status">{attachmentMessage}</div>}
      {toolsOpen && <div className="chat-popover chat-tools-menu" role="menu" aria-label="Инструменты"
        onKeyDown={event => menuKeyboard(event, () => setToolsOpen(false), plusButton.current)}>
        <button type="button" role="menuitem" onClick={() => {
          setToolsOpen(false)
          fileInput.current?.click()
        }}><Icon name="image" /><span>Изображение</span></button>
        {tools.map(item => <button type="button" role="menuitem" key={item.id}
          className={tool === item.id ? 'selected' : ''} aria-pressed={tool === item.id}
          onClick={() => selectTool(item.id)}>
          <Icon name={item.icon} /><span>{item.label}</span>
        </button>)}
      </div>}
      {modelOpen && <div className="chat-popover chat-model-menu" role="menu" aria-label="Модели"
        onKeyDown={event => menuKeyboard(event, () => setModelOpen(false), modelButton.current)}>
        {models.map(item => <button type="button" role="menuitemradio"
          aria-checked={selectedModel?.id === item.id}
          className={selectedModel?.id === item.id ? 'selected' : ''}
          key={item.id} onClick={() => selectModel(item.id)}>
          <span className="chat-model-option">
            <strong>{item.label}</strong>
            <small>{item.description}</small>
          </span>
          {selectedModel?.id === item.id && <Icon name="check" />}
        </button>)}
      </div>}
    </form>
    <div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
  </div>
}
