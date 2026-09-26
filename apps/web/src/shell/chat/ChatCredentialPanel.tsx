import { useState } from 'react'
import type { AuthView, CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import {
  ProviderCredentialCard, type ChatProviderId,
} from './ProviderCredentialCard'

const providers = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'openrouter', label: 'OpenRouter' },
] as const

function credentialFor(
  credentials: CredentialView[], provider: ChatProviderId,
) {
  return credentials.find(item => item.provider === provider) ?? null
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
  const [busyProvider, setBusyProvider] = useState<ChatProviderId | null>(null)
  const connected = providers.filter(
    item => credentialFor(credentials, item.id)?.verified).length

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
      <p>API keys хранятся зашифрованными в аккаунте и не показываются после сохранения.</p>
      <div className="chat-provider-list">
        {providers.map(provider => <ProviderCredentialCard
          key={provider.id}
          auth={auth}
          provider={provider.id}
          label={provider.label}
          credential={credentialFor(credentials, provider.id)}
          busyProvider={busyProvider}
          onBusy={setBusyProvider}
          onChange={onChange}
          onDisabled={onDisabled}
          onError={onError}
        />)}
      </div>
    </div>}
  </>
}
