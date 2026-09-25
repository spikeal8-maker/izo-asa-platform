import { useState, type FormEvent } from 'react'
import {
  apiRequest, chatProblem, type AuthView, type CredentialView,
} from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'

const providers = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'openrouter', label: 'OpenRouter' },
] as const
type Provider = (typeof providers)[number]['id']

function credentialFor(credentials: CredentialView[], provider: Provider) {
  return credentials.find(item => item.provider === provider) ?? null
}

function credentialStatus(
  credential: CredentialView | null, verifyFailed: boolean,
) {
  const savedUnverified = Boolean(
    credential?.configured && credential.enabled && !credential.verified)
  if (credential?.verified) return { text: 'подключён', className: 'is-ok' }
  if (savedUnverified) return verifyFailed
    ? { text: 'проверка не пройдена', className: 'is-error' }
    : { text: 'сохранён, не проверен', className: 'is-saved' }
  return { text: 'не подключён', className: 'is-off' }
}

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
  const [busyProvider, setBusyProvider] = useState<Provider | null>(null)
  const [keys, setKeys] = useState<Record<Provider, string>>({
    deepseek: '', openrouter: '',
  })
  const [verifyFailed, setVerifyFailed] = useState<Record<Provider, boolean>>({
    deepseek: false, openrouter: false,
  })
  const connected = providers.filter(
    item => credentialFor(credentials, item.id)?.verified).length

  function markVerifyFailed(provider: Provider, value: boolean) {
    setVerifyFailed(current => ({ ...current, [provider]: value }))
  }

  async function verify(provider: Provider, view: CredentialView) {
    if (!view.revision) return
    const next = await apiRequest<CredentialView>(
      `/api/v1/chat/credentials/${provider}/verify`, {
        method: 'POST',
        csrf: auth.csrf_token,
        timeoutMs: 20000,
        data: {
          operation_id: crypto.randomUUID(),
          expected_revision: view.revision,
        },
      })
    onChange(next)
    markVerifyFailed(provider, false)
  }

  async function save(provider: Provider, event: FormEvent) {
    event.preventDefault()
    const key = keys[provider].trim()
    const credential = credentialFor(credentials, provider)
    if (!key || busyProvider) return
    setBusyProvider(provider)
    markVerifyFailed(provider, false)
    onError('')
    try {
      const saved = await apiRequest<CredentialView>(
        `/api/v1/chat/credentials/${provider}`, {
          method: 'POST',
          csrf: auth.csrf_token,
          data: {
            operation_id: crypto.randomUUID(),
            key,
            expected_revision: credential?.revision ?? null,
          },
        })
      setKeys(current => ({ ...current, [provider]: '' }))
      onChange(saved)
      try {
        await verify(provider, saved)
      } catch (reason) {
        markVerifyFailed(provider, true)
        onError(`Ключ ${provider === 'deepseek' ? 'DeepSeek' : 'OpenRouter'} сохранён. Проверка не пройдена. ${chatProblem(reason)}`)
      }
    } catch (reason) {
      setKeys(current => ({ ...current, [provider]: '' }))
      onError(chatProblem(reason))
    } finally {
      setBusyProvider(null)
    }
  }

  async function verifyAgain(provider: Provider) {
    const credential = credentialFor(credentials, provider)
    if (!credential || busyProvider) return
    setBusyProvider(provider)
    markVerifyFailed(provider, false)
    onError('')
    try {
      await verify(provider, credential)
    } catch (reason) {
      markVerifyFailed(provider, true)
      onError(`Ключ ${provider === 'deepseek' ? 'DeepSeek' : 'OpenRouter'} сохранён. Проверка не пройдена. ${chatProblem(reason)}`)
    } finally {
      setBusyProvider(null)
    }
  }

  async function disable(provider: Provider) {
    const credential = credentialFor(credentials, provider)
    if (!credential?.revision || busyProvider) return
    setBusyProvider(provider)
    onError('')
    try {
      const next = await apiRequest<CredentialView>(
        `/api/v1/chat/credentials/${provider}/disable`, {
          method: 'POST',
          csrf: auth.csrf_token,
          data: {
            operation_id: crypto.randomUUID(),
            expected_revision: credential.revision,
          },
        })
      markVerifyFailed(provider, false)
      onDisabled(next)
    } catch (reason) {
      onError(chatProblem(reason))
    } finally {
      setBusyProvider(null)
    }
  }

  return <>
    <button type="button" className="chat-credential-toggle"
      aria-label="Настройки DeepSeek и OpenRouter" aria-expanded={open}
      onClick={() => setOpen(value => !value)}>
      <Icon name="sliders" />
      <span className={connected === providers.length
        ? 'is-ok' : connected ? 'is-saved' : 'is-off'} aria-hidden="true" />
      <strong>Провайдеры</strong>
    </button>
    {open && <div className="chat-credential-popover" role="dialog"
      aria-label="Провайдеры">
      <h2>Провайдеры</h2>
      <p>API keys хранятся зашифрованными в аккаунте и никогда не показываются после сохранения.</p>
      <div className="chat-provider-list">
        {providers.map(provider => {
          const credential = credentialFor(credentials, provider.id)
          const status = credentialStatus(
            credential, verifyFailed[provider.id])
          const busy = busyProvider === provider.id
          return <form className="chat-provider-card" key={provider.id}
            onSubmit={event => void save(provider.id, event)}>
            <div className="chat-provider-card-head">
              <strong>{provider.label}</strong>
              <span className={`chat-credential-status ${status.className}`}>
                {status.text}
              </span>
            </div>
            <label className="chat-credential-key">
              <span>Новый API key {provider.label}</span>
              <input type="password" autoComplete="off"
                value={keys[provider.id]}
                onChange={event => setKeys(current => ({
                  ...current, [provider.id]: event.target.value,
                }))}
                aria-label={`Новый API key ${provider.label}`}
                placeholder={`Введите ${provider.label} API key`} />
            </label>
            <div className="chat-credential-actions">
              <button type="submit"
                disabled={Boolean(busyProvider) || !keys[provider.id].trim()}>
                {credential?.configured
                  ? `Заменить и проверить ${provider.label}`
                  : `Сохранить и проверить ${provider.label}`}
              </button>
              {credential?.configured && <button type="button" className="secondary"
                disabled={Boolean(busyProvider)}
                onClick={() => void verifyAgain(provider.id)}>
                Проверить
              </button>}
              {credential?.configured && <button type="button" className="secondary"
                disabled={Boolean(busyProvider)}
                onClick={() => void disable(provider.id)}>
                Отключить
              </button>}
              {busy && <span className="chat-provider-busy" role="status">Проверяем…</span>}
            </div>
          </form>
        })}
      </div>
    </div>}
  </>
}
