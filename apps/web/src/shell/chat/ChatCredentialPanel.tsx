import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiRequest, chatProblem, type AuthView, type CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'

const providers = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'openrouter', label: 'OpenRouter' },
] as const

const credentialFor = (credentials: CredentialView[], provider: ChatProviderId) =>
  credentials.find(item => item.provider === provider)

export function ChatCredentialPanel({
  auth, credentials, onChange, onDisabled, onError,
}: {
  auth: AuthView
  credentials: CredentialView[]
  onChange: (value: CredentialView) => void
  onDisabled: (value: CredentialView) => void
  onError: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [busyProvider, setBusyProvider] = useState<ChatProviderId | null>(null)
  const wrapper = useRef<HTMLDivElement>(null)
  const firstRun = credentials.length > 0 && credentials.every(item => !item.configured)
  const connected = providers.filter(
    item => credentialFor(credentials, item.id)?.verified).length
  const deepseekOnly = connected === 1 && credentialFor(credentials, 'deepseek')?.verified

  useEffect(() => {
    if (firstRun) setOpen(true)
  }, [auth.account.id, firstRun])

  useEffect(() => {
    if (!open) return
    const dismiss = (event: PointerEvent) => {
      if (event.target instanceof Node && !wrapper.current?.contains(event.target)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false); wrapper.current?.querySelector('button')?.focus()
      }
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return <div ref={wrapper} className="chat-provider-panel-anchor">
    <button type="button" className="chat-credential-toggle"
      aria-label={deepseekOnly ? 'DeepSeek подключён' : 'Настройки DeepSeek и OpenRouter'} aria-expanded={open}
      onClick={() => setOpen(value => !value)}>
      <Icon name="sliders" />
      <span className={connected === providers.length
        ? 'is-ok' : connected ? 'is-saved' : 'is-off'} aria-hidden="true" />
      <strong>Провайдеры</strong>
    </button>
    {open && <div className="chat-credential-popover" role="dialog"
      aria-label="Провайдеры">
      <h2>Провайдеры</h2>
      <p>Ключи шифруются и не показываются после сохранения.</p>
      <div className="chat-provider-list">
        {providers.map(provider => <ProviderCredentialCard
          key={`${auth.account.id}:${provider.id}`}
          auth={auth}
          provider={provider.id}
          label={provider.label}
          credential={credentialFor(credentials, provider.id)}
          autoEntry={firstRun && provider.id === 'deepseek'}
          busyProvider={busyProvider}
          onBusy={setBusyProvider}
          onChange={onChange}
          onDisabled={onDisabled}
          onError={onError}
        />)}
      </div>
      <p className="chat-provider-model-hint">Модели — в меню у поля ввода.</p>
    </div>}
  </div>
}

type ChatProviderId = 'deepseek' | 'openrouter'

function ProviderCredentialCard({
  auth, provider, label, credential, autoEntry, busyProvider,
  onBusy, onChange, onDisabled, onError,
}: {
  auth: AuthView
  provider: ChatProviderId
  label: string
  credential?: CredentialView
  autoEntry: boolean
  busyProvider: ChatProviderId | null
  onBusy: (provider: ChatProviderId | null) => void
  onChange: (value: CredentialView) => void
  onDisabled: (value: CredentialView) => void
  onError: (message: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [entryDismissed, setEntryDismissed] = useState(false)
  const [key, setKey] = useState('')
  const [verifyFailed, setVerifyFailed] = useState(false)
  const busy = busyProvider === provider
  const blocked = busyProvider !== null
  const showKeyForm = editing || (autoEntry && !entryDismissed)

  const status = credential?.verified
    ? { text: 'Подключён', className: 'is-ok' }
    : credential?.configured && credential.enabled
      ? { text: verifyFailed ? 'Проверка не пройдена' : 'Сохранён, не проверен', className: verifyFailed ? 'is-error' : 'is-saved' }
      : { text: 'Не подключён', className: 'is-off' }

  async function verify(view: CredentialView) {
    if (!view.revision) return
    const next = await apiRequest<CredentialView>(
      `/api/v1/chat/credentials/${provider}/verify`, {
        method: 'POST', csrf: auth.csrf_token, timeoutMs: 20000,
        data: {
          operation_id: crypto.randomUUID(),
          expected_revision: view.revision,
        },
      })
    onChange(next)
    setVerifyFailed(false)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    const value = key.trim()
    if (!value || blocked) return
    onBusy(provider); setVerifyFailed(false); onError('')
    try {
      const saved = await apiRequest<CredentialView>(
        `/api/v1/chat/credentials/${provider}`, {
          method: 'POST', csrf: auth.csrf_token,
          data: {
            operation_id: crypto.randomUUID(), key: value,
            expected_revision: credential?.revision ?? null,
          },
        })
      setKey(''); setEditing(false); onChange(saved)
      try {
        await verify(saved)
      } catch (reason) {
        setVerifyFailed(true)
        onError(`Ключ ${label} сохранён. Проверка не пройдена. ${chatProblem(reason)}`)
      }
    } catch (reason) {
      setKey('')
      onError(chatProblem(reason))
    } finally {
      onBusy(null)
    }
  }

  async function verifyAgain() {
    if (!credential || blocked) return
    onBusy(provider); setVerifyFailed(false); onError('')
    try {
      await verify(credential)
    } catch (reason) {
      setVerifyFailed(true)
      onError(`Ключ ${label} сохранён. Проверка не пройдена. ${chatProblem(reason)}`)
    } finally {
      onBusy(null)
    }
  }

  async function disable() {
    if (!credential?.revision || blocked) return
    onBusy(provider); onError('')
    try {
      const next = await apiRequest<CredentialView>(
        `/api/v1/chat/credentials/${provider}/disable`, {
          method: 'POST', csrf: auth.csrf_token,
          data: {
            operation_id: crypto.randomUUID(),
            expected_revision: credential.revision,
          },
        })
      setVerifyFailed(false); setEditing(false); setKey(''); onDisabled(next)
    } catch (reason) {
      onError(chatProblem(reason))
    } finally {
      onBusy(null)
    }
  }

  return <section className="chat-provider-card" aria-label={label}>
    <div className="chat-provider-card-head">
      <div className="chat-provider-identity">
        <strong>{label}</strong>
        <span className={`chat-provider-dot ${status.className}`} aria-hidden="true" />
        <span className={`chat-credential-status ${status.className}`}>{status.text}</span>
      </div>
      {!showKeyForm && <div className="chat-provider-actions">
        {credential?.configured
          ? <>
              <button type="button" className="chat-provider-button secondary"
                disabled={blocked} onClick={() => void verifyAgain()}>Проверить</button>
              <button type="button" className="chat-provider-button secondary"
                autoFocus={entryDismissed}
                disabled={blocked} onClick={() => setEditing(true)}>Заменить ключ</button>
              <button type="button" className="chat-provider-button secondary"
                disabled={blocked} onClick={() => void disable()}>Отключить</button>
            </>
          : <button type="button" className="chat-provider-button secondary"
              autoFocus={entryDismissed}
              disabled={blocked} onClick={() => setEditing(true)}>Добавить ключ</button>}
      </div>}
    </div>
    {showKeyForm && <form className="chat-provider-key-form" onSubmit={event => void save(event)}>
      <label className="chat-credential-key">
        <span>{provider === 'deepseek' ? 'API ключ DeepSeek' : `Новый API key ${label}`}</span>
        <input type="password" autoComplete="off" autoFocus value={key}
          onChange={event => setKey(event.target.value)}
          placeholder={`Введите ${label} API key`} />
      </label>
      <div className="chat-provider-actions">
        <button type="submit" className="chat-provider-button primary"
          disabled={blocked || !key.trim()}>
          {credential?.configured ? 'Заменить и проверить' : 'Сохранить и проверить'}
        </button>
        <button type="button" className="chat-provider-button secondary"
          disabled={blocked} onClick={() => { setEditing(false); setEntryDismissed(true); setKey('') }}>
          Отмена
        </button>
        {busy && <span className="chat-provider-busy" role="status">Проверяем…</span>}
      </div>
    </form>}
  </section>
}
