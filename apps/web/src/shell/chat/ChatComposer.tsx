import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChatPolicyView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { selectedTextModel, textModels, toolById, type Tool } from './modelCatalog'
import { ComposerMenus } from './ComposerMenus'
import { useChatAttachment } from './AttachmentControl'
import { useComposerLayout } from './composerLayout'
import { useVoiceCapture } from './useVoiceCapture'
import './ChatComposer.css'
import './ModelMenu.css'

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
  const plusButton = useRef<HTMLButtonElement>(null)
  const modelButton = useRef<HTMLButtonElement>(null)
  const voice = useVoiceCapture()
  const models = textModels(policy)
  const selectedModel = selectedTextModel(policy, selectedModelId)

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

  const visionModel = models.find(item => item.vision) ?? null
  const attachmentControl = useChatAttachment({
    policy,
    selectedVision: selectedModel?.vision ?? false,
    visionModel,
    onModelChange,
  })
  const attachment = attachmentControl.attachment
  const forcedExpanded = voice.active || Boolean(tool) || Boolean(attachment)
  const layout = useComposerLayout(draft, forcedExpanded)
  const attachImage = async (file: File) => {
    setTool(null)
    await attachmentControl.add(file)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || voice.active || busy || disabled || !selectedModel) return
    if (tool) {
      onUnsupported()
      return
    }
    if (attachment && !selectedModel.vision) return
    if (!await onSend(text, selectedModel.id, attachment)) return
    setDraft('')
    attachmentControl.remove()
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
    if (attachment && !next.vision) return
    onModelChange(next.id)
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
      {attachmentControl.input}
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
        {attachmentControl.preview}
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
      {attachmentControl.message && <div className="chat-attachment-note" role="status">{attachmentControl.message}</div>}
      <ComposerMenus
        toolsOpen={toolsOpen} modelOpen={modelOpen} tool={tool}
        models={models} selectedModelId={selectedModel?.id ?? null}
        plusButton={plusButton} modelButton={modelButton}
        inputRef={attachmentControl.inputRef}
        onCloseTools={() => setToolsOpen(false)}
        onCloseModels={() => setModelOpen(false)}
        onSelectTool={selectTool} onSelectModel={selectModel}
      />
    </form>
    <div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
  </div>
}
