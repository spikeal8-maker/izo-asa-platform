import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiRequest, type AuthView, type ChatPolicyView, type CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { autoModel, modelAvailable, providerFor, textModels, type ChatDisplayPolicy, type ChatModel } from './modelCatalog'
import { useComposerLayout } from './composerLayout'
import { ModelPicker } from './ModelPicker'
import { fetchOpenRouterCatalog } from './useChatCatalog'
import { useVoiceCapture } from './useVoiceCapture'
import './ChatComposer.css'

export function ChatComposer({ auth, policy, credentials, catalogError, busy, stoppable, disabled,
  onSend, onStop }: {
  auth: AuthView | null | undefined
  policy: ChatDisplayPolicy | null
  credentials: CredentialView[]
  catalogError: string
  busy: boolean
  stoppable: boolean
  disabled: boolean
  onSend: (text: string, modelId: string) => Promise<boolean>
  onStop: () => void
}) {
  const [draft, setDraft] = useState('')
  const [modelOpen, setModelOpen] = useState(false)
  const [model, setModel] = useState<ChatModel>(autoModel)
  const [modelError, setModelError] = useState('')
  const [checkingPrice, setCheckingPrice] = useState(false)
  const modelButton = useRef<HTMLButtonElement>(null)
  const preflight = useRef<AbortController | null>(null)
  const voice = useVoiceCapture()
  const layout = useComposerLayout(draft, voice.active)
  const models = textModels(policy)
  const resolvedModel = model.id === 'auto'
    ? models.find(item => item.id === policy?.default_model) : models.find(item => item.id === model.id)
  const providerReady = Boolean(resolvedModel && modelAvailable(resolvedModel, credentials))

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
    if (!text || voice.active || busy || disabled || preflight.current) return
    if (!resolvedModel) {
      setModelError('Выбранная модель больше недоступна. Выберите другую модель или обновите страницу.')
      return
    }
    if (!providerReady) {
      setModelError(`Подключите и проверьте API key ${providerFor(resolvedModel) === 'openrouter' ? 'OpenRouter' : 'DeepSeek'}.`)
      return
    }
    const controller = new AbortController()
    preflight.current = controller; setCheckingPrice(true)
    setModelOpen(false)
    try {
      let latest: ChatPolicyView
      try {
        latest = await apiRequest<ChatPolicyView>('/api/v1/chat/policy', {
          signal: controller.signal, timeoutMs: 6000,
        })
      } catch {
        if (!controller.signal.aborted) setModelError('Не удалось проверить цену. Повторите попытку позднее.')
        return
      }
      if (controller.signal.aborted) return
      if (latest.revision !== policy?.revision) {
        setModelError('Модели или цены изменились — обновите чат перед отправкой.')
        return
      }
      if (resolvedModel.catalog_dynamic) {
        try {
          const current = await fetchOpenRouterCatalog(controller.signal)
          if (current.stale || !current.models.some(item => item.id === resolvedModel.id)) {
            setModelError('Каталог OpenRouter изменился — обновите список моделей перед отправкой.')
            return
          }
        } catch {
          if (!controller.signal.aborted) setModelError('Не удалось проверить каталог OpenRouter. Повторите позже.')
          return
        }
      } else if (!latest.models.some(item => item.id === resolvedModel.id)) {
        setModelError('Выбранная модель больше недоступна. Выберите другую модель или обновите страницу.')
        return
      }
      if (controller.signal.aborted) return
      setModelError('')
      if (!await onSend(text, resolvedModel.id)) return
      setDraft('')
      requestAnimationFrame(() => layout.textareaRef.current?.focus())
    } finally {
      if (preflight.current === controller) preflight.current = null
      if (!controller.signal.aborted) setCheckingPrice(false)
    }
  }

  function selectModel(next: ChatModel) {
    if (preflight.current) return
    setModel(next); setModelError(''); setModelOpen(false)
    requestAnimationFrame(() => modelButton.current?.focus())
  }

  return <div className="chat-composer-wrap">
    <form ref={layout.formRef}
      className={`chat-composer ${layout.expanded ? 'is-expanded' : 'is-compact'} ${voice.active ? 'voice-active' : ''}`}
      data-layout={layout.expanded ? 'expanded' : 'compact'} onSubmit={event => void submit(event)}>
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
            placeholder="Спросите что-нибудь" disabled={disabled || busy || checkingPrice}
            onChange={event => { if (!preflight.current) setDraft(event.target.value) }}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault(); event.currentTarget.form?.requestSubmit()
              }
            }} />}
      <button type="button" className="chat-circle-button chat-composer-plus"
        data-composer-control="compact" aria-label="Добавить" title="Вложения пока недоступны"
        disabled><Icon name="plus" /></button>
      <ModelPicker open={modelOpen} model={model} models={models}
        credentials={credentials} accountId={auth?.account.id} catalogError={catalogError}
        defaultModelId={policy?.default_model} busy={busy || checkingPrice}
        buttonRef={modelButton} onToggle={() => setModelOpen(value => !value)}
        onClose={() => setModelOpen(false)} onSelect={selectModel} />
      <button type="button" className={`chat-circle-button chat-mic-button ${voice.active ? 'active' : ''}`}
        data-composer-control="compact" aria-label={voice.active ? 'Остановить микрофон' : 'Микрофон'}
        disabled={busy || checkingPrice} onClick={() => voice.active ? voice.stop() : void voice.start()}>
        <Icon name="mic" />
      </button>
      {busy
        ? <button type="button" className="chat-send-button" data-composer-control="compact"
            aria-label="Остановить ответ" disabled={!stoppable} onClick={onStop}><Icon name="close" /></button>
        : <button type="submit" className="chat-send-button" data-composer-control="compact"
            aria-label={checkingPrice ? 'Проверяем модель и цену' : 'Отправить'}
            disabled={disabled || !draft.trim() || voice.active || checkingPrice}>
            <Icon name="send" />
          </button>}
      {voice.error && <div className="chat-voice-error" role="alert">{voice.error}</div>}
      {modelError && <div className="chat-voice-error" role="alert">{modelError}</div>}
    </form>
    <div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
  </div>
}
