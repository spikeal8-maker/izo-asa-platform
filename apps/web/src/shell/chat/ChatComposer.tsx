import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Icon } from '../../shared/ui/Icon'
import type { ChatModel } from './types'
import { menuKeyboard, useComposerLayout } from './composerLayout'
import './ChatComposer.css'

export function ChatComposer({ models, model, busy, disabled, onModelChange, onSend, onStop }: {
  models: ChatModel[]
  model: ChatModel | null
  busy: boolean
  disabled: boolean
  onModelChange: (model: ChatModel) => void
  onSend: (text: string) => void
  onStop: () => void
}) {
  const [draft, setDraft] = useState('')
  const [modelOpen, setModelOpen] = useState(false)
  const modelButton = useRef<HTMLButtonElement>(null)
  const layout = useComposerLayout(draft, false)

  useEffect(() => {
    if (!modelOpen) return
    const dismiss = (event: PointerEvent) => {
      const target = event.target
      if (target instanceof Element && !target.closest('.chat-model-selector,.chat-model-menu')) {
        setModelOpen(false)
      }
    }
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setModelOpen(false)
      requestAnimationFrame(() => modelButton.current?.focus())
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', escape)
    }
  }, [modelOpen])

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy || disabled || !model) return
    onSend(text)
    setDraft('')
    requestAnimationFrame(() => layout.textareaRef.current?.focus())
  }

  return <div className="chat-composer-wrap">
    <form ref={layout.formRef}
      className={`chat-composer ${layout.expanded ? 'is-expanded' : 'is-compact'}`}
      data-layout={layout.expanded ? 'expanded' : 'compact'} onSubmit={submit}>
      <div ref={layout.measureRef} className="chat-composer-measure" aria-hidden="true" />
      <textarea ref={layout.textareaRef} rows={1} value={draft} aria-label="Сообщение"
        placeholder={disabled ? 'Подключите ключ DeepSeek' : 'Спросите что-нибудь'}
        disabled={disabled || busy}
        onChange={event => setDraft(event.target.value)}
        onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            event.currentTarget.form?.requestSubmit()
          }
        }} />

      <button type="button" className="chat-circle-button chat-composer-plus"
        data-composer-control="compact" aria-label="Вложения пока недоступны" disabled>
        <Icon name="plus" />
      </button>

      <button ref={modelButton} type="button" className="chat-model-selector"
        data-composer-control="compact" aria-label="Выбрать модель"
        aria-expanded={modelOpen} disabled={disabled || busy || models.length === 0}
        onClick={() => setModelOpen(value => !value)}>
        <span>{model?.label ?? 'Модель'}</span><Icon name="chevron" />
      </button>

      <button type="button" className="chat-circle-button chat-mic-button"
        data-composer-control="compact" aria-label="Микрофон пока недоступен" disabled>
        <Icon name="mic" />
      </button>

      {busy
        ? <button type="button" className="chat-send-button" data-composer-control="compact"
            aria-label="Остановить ответ" onClick={onStop}><Icon name="close" /></button>
        : <button type="submit" className="chat-send-button" data-composer-control="compact"
            aria-label="Отправить" disabled={disabled || !draft.trim() || !model}>
            <Icon name="send" />
          </button>}

      {modelOpen && <div className="chat-popover chat-model-menu" role="menu" aria-label="Модели"
        onKeyDown={event => menuKeyboard(event, () => setModelOpen(false), modelButton.current)}>
        <div className="chat-model-category">
          <div className="chat-model-category-list">
            {models.map(item => <button type="button" role="menuitemradio"
              aria-checked={model?.id === item.id}
              className={model?.id === item.id ? 'selected' : ''}
              key={item.id} onClick={() => {
                onModelChange(item)
                setModelOpen(false)
                requestAnimationFrame(() => modelButton.current?.focus())
              }}>
              <span>{item.label}</span>{model?.id === item.id && <Icon name="check" />}
            </button>)}
          </div>
        </div>
      </div>}
    </form>
    <div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
  </div>
}
