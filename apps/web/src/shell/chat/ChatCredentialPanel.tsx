import { useState, type FormEvent } from 'react'
import {
  apiRequest, chatProblem, type AuthView, type CredentialView,
} from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'

export function ChatCredentialPanel({
  auth, credential, onChange, onDisabled, onError,
}: {
  auth: AuthView
  credential: CredentialView | null
  onChange: (value: CredentialView) => void
  onDisabled: (value: CredentialView) => void
  onError: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState('')
  const [verifyFailed, setVerifyFailed] = useState(false)
  const savedUnverified = Boolean(
    credential?.configured && credential.enabled && !credential.verified)
  const status = credential?.verified
    ? 'подключён'
    : savedUnverified
      ? (verifyFailed ? 'проверка не пройдена' : 'сохранён, не проверен')
      : 'не подключён'
  const statusClass = credential?.verified
    ? 'is-ok'
    : savedUnverified
      ? (verifyFailed ? 'is-error' : 'is-saved')
      : 'is-off'

  async function verify(view: CredentialView) {
    if (!view.revision) return
    const next = await apiRequest<CredentialView>('/api/v1/chat/credential/verify', {
      method: 'POST',
      csrf: auth.csrf_token,
      timeoutMs: 20000,
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
    if (!key.trim() || busy) return
    setBusy(true)
    setVerifyFailed(false)
    onError('')
    try {
      const saved = await apiRequest<CredentialView>('/api/v1/chat/credential', {
        method: 'POST',
        csrf: auth.csrf_token,
        data: {
          operation_id: crypto.randomUUID(),
          key: key.trim(),
          expected_revision: credential?.revision ?? null,
        },
      })
      setKey('')
      onChange(saved)
      try {
        await verify(saved)
      } catch (reason) {
        setVerifyFailed(true)
        onError(`Ключ сохранён. Проверка не пройдена. ${chatProblem(reason)}`)
      }
    } catch (reason) {
      setKey('')
      onError(chatProblem(reason))
    } finally {
      setBusy(false)
    }
  }

  async function verifyAgain() {
    if (!credential || busy) return
    setBusy(true)
    setVerifyFailed(false)
    onError('')
    try {
      await verify(credential)
    } catch (reason) {
      setVerifyFailed(true)
      onError(`Ключ сохранён. Проверка не пройдена. ${chatProblem(reason)}`)
    } finally {
      setBusy(false)
    }
  }

  async function disable() {
    if (!credential?.revision || busy) return
    setBusy(true)
    onError('')
    try {
      const next = await apiRequest<CredentialView>('/api/v1/chat/credential/disable', {
        method: 'POST',
        csrf: auth.csrf_token,
        data: {
          operation_id: crypto.randomUUID(),
          expected_revision: credential.revision,
        },
      })
      setVerifyFailed(false)
      onDisabled(next)
    } catch (reason) {
      onError(chatProblem(reason))
    } finally {
      setBusy(false)
    }
  }

  return <>
    <button type="button" className="chat-credential-toggle"
      aria-label="Настройки DeepSeek" aria-expanded={open}
      onClick={() => setOpen(value => !value)}>
      <Icon name="sliders" />
      <span className={statusClass} aria-hidden="true" />
      <strong>DeepSeek</strong>
    </button>
    {open && <form className="chat-credential-popover" onSubmit={event => void save(event)}>
      <h2>DeepSeek API</h2>
      <p className={`chat-credential-status ${statusClass}`}>
        Статус: {status}
      </p>
      <p>Ключ хранится зашифрованным в аккаунте и никогда не показывается после сохранения.</p>
      <label className="chat-credential-key">
        <span>Новый API key</span>
        <input type="password" autoComplete="off" value={key}
          onChange={event => setKey(event.target.value)}
          aria-label="Новый API key" placeholder="Введите новый API key" />
      </label>
      <div className="chat-credential-actions">
        <button type="submit" disabled={busy || !key.trim()}>
          {credential?.configured ? 'Заменить и проверить' : 'Сохранить и проверить'}
        </button>
        {credential?.configured && <button type="button" className="secondary"
          disabled={busy} onClick={() => void verifyAgain()}>
          Проверить
        </button>}
        {credential?.configured && <button type="button" className="secondary"
          disabled={busy} onClick={() => void disable()}>
          Отключить
        </button>}
      </div>
    </form>}
  </>
}
