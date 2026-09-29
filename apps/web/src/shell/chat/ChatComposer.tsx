import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { AuthView, CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { autoModel, modelAvailable, providerFor, textModels, type ChatDisplayPolicy, type ChatModel } from './modelCatalog'
import { useComposerLayout } from './composerLayout'
import { ModelPicker } from './ModelPicker'
import { chatPreflight } from './useChatPreflight'
import { useChatAttachment } from './AttachmentControl'
import type { ChatAttachmentDraft } from './chatAttachments'
import { useVoiceCapture } from './useVoiceCapture'
import './ChatComposer.css'

export function ChatComposer({ auth, policy, credentials, catalogError, busy, stoppable, disabled,
  onSend, onStop, onRefreshPolicy }: {
  auth: AuthView | null | undefined
  policy: ChatDisplayPolicy | null
  credentials: CredentialView[]
  catalogError: string
  busy: boolean
  stoppable: boolean
  disabled: boolean
  onSend: (text: string, modelId: string, attachments: ChatAttachmentDraft[]) => Promise<boolean>
  onStop: () => void
  onRefreshPolicy: () => Promise<unknown>
}) {
  const [draft, setDraft] = useState('')
  const [modelOpen, setModelOpen] = useState(false)
  const [model, setModel] = useState<ChatModel>(autoModel)
  const [modelError, setModelError] = useState('')
  const [checkingPrice, setCheckingPrice] = useState(false)
  const locked = busy || checkingPrice
  const modelButton = useRef<HTMLButtonElement>(null)
  const preflight = useRef<AbortController | null>(null)
  const voice = useVoiceCapture()
  const models = textModels(policy).map(item => policy?.max_attachments && item.catalog_dynamic && item.vision
    ? { ...item, description: 'Модель принимает изображения' } : item)
  const resolvedModel = model.id === 'auto'
    ? models.find(item => item.id === policy?.default_model) : models.find(item => item.id === model.id)
  const providerReady = Boolean(resolvedModel && modelAvailable(resolvedModel, credentials))
  const images = useChatAttachment({ policy, accountId: auth?.account.id,
    locked,
    selectedVision: Boolean(resolvedModel?.vision && providerReady && !resolvedModel.catalog_stale),
    visionModel: models.find(item => item.vision && !item.catalog_stale && modelAvailable(item, credentials)) ?? null,
    onModelChange: setModel })
  const layout = useComposerLayout(draft, voice.active || images.attachments.length > 0)

  useEffect(() => () => preflight.current?.abort(), [])
  useEffect(() => {
    if (!modelOpen) return
    const dismiss = (event: PointerEvent) => {
      if (event.target instanceof Element && !event.target.closest('.chat-model-selector,.chat-model-menu'))
        setModelOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault(); setModelOpen(false)
      requestAnimationFrame(() => modelButton.current?.focus())
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', escape)
    }
  }, [modelOpen])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if ((!text && !images.attachments.length) || voice.active || busy || disabled
      || images.validating || preflight.current) return
    if (!resolvedModel) {
      setModelError('Выбранная модель больше недоступна. Выберите другую.')
      return
    }
    if (!providerReady) {
      setModelError(`Подключите и проверьте API key ${providerFor(resolvedModel) === 'openrouter' ? 'OpenRouter' : 'DeepSeek'}.`)
      return
    }
    if (images.attachments.length && !resolvedModel.vision) {
      setModelError('Выберите модель для изображений.')
      return
    }
    const controller = new AbortController()
    preflight.current = controller; setCheckingPrice(true)
    setModelOpen(false)
    try {
      const problem = await chatPreflight(policy, resolvedModel, images.attachments.length, controller.signal)
      if (problem) { setModelError(problem); await onRefreshPolicy().catch(() => {}); return }
      if (controller.signal.aborted) return
      setModelError('')
      if (!await onSend(text, resolvedModel.id, images.attachments)) return
      setDraft(''); images.clear(images.attachments)
      requestAnimationFrame(() => layout.textareaRef.current?.focus())
    } finally {
      if (preflight.current === controller) preflight.current = null
      if (!controller.signal.aborted) setCheckingPrice(false)
    }
  }

  function selectModel(next: ChatModel) {
    if (preflight.current) return
    if (images.attachments.length && next.id !== 'auto' && !next.vision) {
      setModelError('Удалите изображения или выберите другую модель.')
      return
    }
    if (images.attachments.length && next.id === 'auto'
      && !models.find(item => item.id === policy?.default_model)?.vision) {
      setModelError('Автомодель не принимает изображения. Выберите другую.')
      return
    }
    setModel(next); setModelError(''); setModelOpen(false)
    requestAnimationFrame(() => modelButton.current?.focus())
  }

  return <div className="chat-composer-wrap">
    <form ref={layout.formRef}
      className={`chat-composer ${layout.expanded ? 'is-expanded' : 'is-compact'} ${images.attachments.length ? 'has-attachments' : ''} ${voice.active ? 'voice-active' : ''}`}
      data-layout={layout.expanded ? 'expanded' : 'compact'} onSubmit={event => void submit(event)}
      onDragOver={event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault() }}
      onDrop={event => { if (!event.dataTransfer.files.length) return; event.preventDefault()
        void images.add(Array.from(event.dataTransfer.files)) }}>
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
            placeholder="Спросите что-нибудь" disabled={disabled || locked}
            onChange={event => { if (!preflight.current) setDraft(event.target.value) }}
            onPaste={event => { const files = Array.from(event.clipboardData.files)
              if (files.length) void images.add(files) }}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault(); event.currentTarget.form?.requestSubmit()
              }
            }} />}
      {images.input}
      {images.preview}
      <button type="button" className="chat-circle-button chat-composer-plus"
        data-composer-control="compact" aria-label="Добавить"
        title={policy?.max_attachments ? 'Добавить изображения' : 'Вложения пока недоступны'}
        disabled={!auth || !policy?.max_attachments || disabled || locked || images.validating}
        onClick={() => images.inputRef.current?.click()}><Icon name="plus" /></button>
      <ModelPicker open={modelOpen} model={model} models={models}
        credentials={credentials} accountId={auth?.account.id} catalogError={catalogError}
        defaultModelId={policy?.default_model} busy={locked}
        buttonRef={modelButton} onToggle={() => setModelOpen(value => !value)}
        onClose={() => setModelOpen(false)} onSelect={selectModel} />
      <button type="button" className={`chat-circle-button chat-mic-button ${voice.active ? 'active' : ''}`}
        data-composer-control="compact" aria-label={voice.active ? 'Остановить микрофон' : 'Микрофон'}
        disabled={locked} onClick={() => voice.active ? voice.stop() : void voice.start()}>
        <Icon name="mic" />
      </button>
      {busy
        ? <button type="button" className="chat-send-button" data-composer-control="compact"
            aria-label="Остановить ответ" disabled={!stoppable} onClick={onStop}><Icon name="close" /></button>
        : <button type="submit" className="chat-send-button" data-composer-control="compact"
            aria-label={checkingPrice ? 'Проверяем модель и цену' : 'Отправить'}
            disabled={disabled || (!draft.trim() && !images.attachments.length) || voice.active || locked || images.validating}>
            <Icon name="send" />
          </button>}
      {voice.error && <div className="chat-voice-error" role="alert">{voice.error}</div>}
      {modelError && <div className="chat-voice-error" role="alert">{modelError}</div>}
      {images.message && <div className="chat-voice-error" role="alert">{images.message}</div>}
    </form>
    <div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
  </div>
}
