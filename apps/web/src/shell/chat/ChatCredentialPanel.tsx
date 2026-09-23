import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, type AuthView, type CredentialView } from '../../shared/api'
import { chatProblem } from './stream'

export function ChatCredentialPanel({ auth, credential, onChange, onDisabled, onError }: {
  auth: AuthView
  credential: CredentialView | null
  onChange: (value: CredentialView) => void
  onDisabled: (value: CredentialView) => void
  onError: (message: string) => void
}) {
  const [open, setOpen] = useState(!credential?.verified)
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState('')

  useEffect(() => {
    if (!credential?.verified) setOpen(true)
  }, [credential?.verified])

  async function verify(view: CredentialView) {
    if (!view.revision) return
    const next = await apiRequest<CredentialView>('/api/v1/chat/credential/verify', {
      method: 'POST', csrf: auth.csrf_token, timeoutMs: 20000,
      data: { operation_id: crypto.randomUUID(), expected_revision: view.revision },
    })
    onChange(next)
    if (next.verified) setOpen(false)
  }
  async function save(event: FormEvent) {
    event.preventDefault()
    if (!key.trim() || busy) return
    setBusy(true); onError('')
    try {
      const saved = await apiRequest<CredentialView>('/api/v1/chat/credential', {
        method: 'POST', csrf: auth.csrf_token,
        data: {
          operation_id: crypto.randomUUID(), key: key.trim(),
          expected_revision: credential?.revision ?? null,
        },
      })
      setKey(''); onChange(saved); await verify(saved)
    } catch (reason) {
      setKey(''); onError(chatProblem(reason))
    } finally { setBusy(false) }
  }

  async function verifyAgain() {
    if (!credential || busy) return
    setBusy(true); onError('')
    try { await verify(credential) }
    catch (reason) { onError(chatProblem(reason)) }
    finally { setBusy(false) }
  }

  async function disable() {
    if (!credential?.revision || busy) return
    setBusy(true); onError('')
    try {
      const next = await apiRequest<CredentialView>('/api/v1/chat/credential/disable', {
        method: 'POST', csrf: auth.csrf_token,
        data: { operation_id: crypto.randomUUID(), expected_revision: credential.revision },
      })
      onDisabled(next); setOpen(true)
    } catch (reason) { onError(chatProblem(reason)) }
    finally { setBusy(false) }
  }
  return <>
    <button type="button" className="chat-credential-toggle" aria-expanded={open}
      onClick={() => setOpen(value => !value)}>
      <span className={credential?.verified ? 'is-ok' : ''} />
      {credential?.verified ? 'DeepSeek подключён' : 'Подключить DeepSeek'}
    </button>
    {open && <form className="chat-credential-popover" onSubmit={event => void save(event)}>
      <h2>Ключ DeepSeek</h2>
      <p>Ключ сохраняется зашифрованным в этом аккаунте и не попадает в историю чата.</p>
      <input type="password" autoComplete="off" value={key}
        onChange={event => setKey(event.target.value)}
        aria-label="API ключ DeepSeek" placeholder="Введите API key" />
      <div className="chat-credential-actions">
        <button type="submit" disabled={busy || !key.trim()}>
          {credential?.configured ? 'Заменить и проверить' : 'Сохранить и проверить'}
        </button>
        {credential?.configured && !credential.verified
          && <button type="button" disabled={busy} onClick={() => void verifyAgain()}>
            Проверить сохранённый
          </button>}
        {credential?.configured && <button type="button" className="secondary"
          disabled={busy} onClick={() => void disable()}>Отключить</button>}
      </div>
    </form>}
  </>
}
