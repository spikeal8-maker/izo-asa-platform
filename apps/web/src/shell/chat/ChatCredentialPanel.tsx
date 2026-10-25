import { useEffect, useRef, useState } from 'react'
import type { AuthView, CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { ProviderCredentialCard, type ChatProviderId } from './ProviderCredentialCard'

const providers = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'openrouter', label: 'OpenRouter' },
] as const

const credentialFor = (credentials: CredentialView[], provider: ChatProviderId) =>
  credentials.find(item => item.provider === provider)

export function ChatCredentialPanel({
  auth, credentials, platformAvailable, onChange, onDisabled, onError,
}: {
  auth: AuthView
  credentials: CredentialView[]
  platformAvailable: boolean | undefined
  onChange: (value: CredentialView) => void
  onDisabled: (value: CredentialView) => void
  onError: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [busyProvider, setBusyProvider] = useState<ChatProviderId | null>(null)
  const wrapper = useRef<HTMLDivElement>(null)
  const firstRun = credentials.length > 0 && credentials.every(item => !item.configured) && platformAvailable === false
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
