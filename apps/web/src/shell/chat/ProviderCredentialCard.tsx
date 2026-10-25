import { useState, type FormEvent } from 'react'
import { ApiError, apiRequest, chatProblem, type AuthView, type CredentialView } from '../../shared/api'
import { providerKeyMismatch, type CredentialProvider } from './providerKeyMismatch'
import './ProviderKeyMismatch.css'

export type ChatProviderId = CredentialProvider

function humanCredentialProblem(reason: unknown, provider: ChatProviderId): string {
  if (reason instanceof ApiError && reason.code === 'credential_provider_mismatch') {
    return provider === 'deepseek'
      ? 'Ключ OpenRouter нельзя сохранить как DeepSeek. Выберите карточку OpenRouter.'
      : 'Ключ DeepSeek нельзя сохранить как OpenRouter. Выберите карточку DeepSeek.'
  }
  return chatProblem(reason)
}


export function ProviderCredentialCard({
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
  const mismatchedKey = providerKeyMismatch(provider, key)

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
    if (mismatchedKey) {
      onError(mismatchedKey)
      return
    }
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
      if (!(reason instanceof ApiError && reason.code === 'credential_provider_mismatch')) setKey('')
      onError(humanCredentialProblem(reason, provider))
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
    {credential?.configured && credential.enabled && !credential.verified && !showKeyForm
      && <p className="chat-provider-key-warning" role="status">
        Ключ сохранён, но не подтверждён провайдером. Проверьте, что он принадлежит {label},
        затем нажмите «Проверить» или «Заменить ключ».
      </p>}
    {showKeyForm && <form className="chat-provider-key-form" onSubmit={event => void save(event)}>
      <label className="chat-credential-key">
        <span>{provider === 'deepseek' ? 'API ключ DeepSeek' : `Новый API key ${label}`}</span>
        <input type="password" autoComplete="off" autoFocus value={key}
          aria-invalid={Boolean(mismatchedKey)}
          onChange={event => { setKey(event.target.value); onError('') }}
          placeholder={`Введите ${label} API key`} />
      </label>
      {mismatchedKey && <p className="chat-provider-key-warning" role="alert">{mismatchedKey}</p>}
      <div className="chat-provider-actions">
        <button type="submit" className="chat-provider-button primary"
          disabled={blocked || !key.trim() || Boolean(mismatchedKey)}>
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
