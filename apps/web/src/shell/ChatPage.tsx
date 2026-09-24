import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, chatProblem, type AuthView, type CredentialView } from '../shared/api'
import { Icon } from '../shared/ui/Icon'
import { Link } from './router'
import { ChatComposer } from './chat/ChatComposer'
import { ChatMessage } from './chat/ChatMessage'
import { ChatSidebar } from './chat/ChatSidebar'
import { useChatRuntime } from './chat/useChatRuntime'
import { useVisualViewport } from './chat/useVisualViewport'
import './chat.css'
import './chat/ChatRuntime.css'

const desktopQuery = '(min-width: 1120px)'

export function ChatPage({ auth, theme, onThemeChange, onLogout }: {
  auth: AuthView | null | undefined
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
}) {
  const runtime = useChatRuntime(auth)
  const [sidebarOpen, setSidebarOpen] = useState(
    () => window.matchMedia(desktopQuery).matches)
  useVisualViewport()

  useEffect(() => {
    const media = window.matchMedia(desktopQuery)
    const sync = () => setSidebarOpen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  function newChat() {
    runtime.newChat()
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  async function openChat(chat: (typeof runtime.history)[number]) {
    await runtime.openChat(chat)
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  const empty = runtime.messages.length === 0
  const disabled = !auth || !runtime.policy || !runtime.credential?.verified
  const composer = <ChatComposer
    policy={runtime.policy}
    busy={runtime.busy}
    stoppable={Boolean(runtime.activeRequestId)}
    disabled={disabled}
    selectedModelId={runtime.model?.id ?? null}
    onModelChange={runtime.setModelId}
    onSend={runtime.send}
    onStop={() => void runtime.stop()}
    onUnsupported={() => runtime.setError(
      'Этот инструмент ещё не подключён к текстовому Chat.')}
  />

  return <section
    className={`chat-page ${empty ? 'is-empty' : ''} ${sidebarOpen ? 'sidebar-open' : ''}`}
    aria-label="Чат ИЗО АСА">
    <ChatSidebar
      auth={auth}
      history={runtime.history}
      currentChatId={runtime.currentChatId}
      busy={runtime.busy}
      theme={theme}
      onThemeChange={onThemeChange}
      onLogout={onLogout}
      onNewChat={newChat}
      onOpenChat={chat => void openChat(chat)}
      onClose={() => setSidebarOpen(false)}
    />
    {sidebarOpen && <button className="chat-drawer-backdrop" aria-label="Закрыть историю"
      onClick={() => setSidebarOpen(false)} />}
    <div className="chat-main">
      <div className="chat-toolbar">
        {!sidebarOpen && <button className="chat-icon-button chat-sidebar-open"
          aria-label="Открыть панель" onClick={() => setSidebarOpen(true)}>
          <Icon name="panel" />
        </button>}
        {auth && <ChatCredentialPanel
          auth={auth}
          credential={runtime.credential}
          onChange={runtime.setCredential}
          onDisabled={runtime.credentialDisabled}
          onError={runtime.setError}
        />}
      </div>
      {empty
        ? <div className="chat-start-state">
            <h1>Чем я могу помочь?</h1>
            {auth === undefined
              ? <p className="chat-start-note" role="status">Проверяем вход…</p>
              : !auth
                ? <p className="chat-start-note">
                    Для сохранённого разговора нужен аккаунт. <Link href="/login">Войти</Link>
                  </p>
                : !runtime.credential?.verified
                  ? <p className="chat-start-note">Подключите и проверьте свой ключ DeepSeek.</p>
                  : null}
            {runtime.error && <div className="chat-runtime-note" role="alert">
              <Icon name="info" /><span>{runtime.error}</span>
            </div>}
            {composer}
          </div>
        : <>
            <div className="chat-scroll" aria-live="polite">
              <div className="chat-column">
                <div className="chat-turns">
                  {auth && runtime.messages.map(message =>
                    <ChatMessage key={message.id} message={message} auth={auth} />)}
                  {runtime.error && <div className="chat-runtime-note" role="alert">
                    <Icon name="info" /><span>{runtime.error}</span>
                  </div>}
                </div>
              </div>
            </div>
            <div className="chat-composer-dock">{composer}</div>
          </>}
    </div>
  </section>
}

function ChatCredentialPanel({ auth, credential, onChange, onDisabled, onError }: {
  auth: AuthView
  credential: CredentialView | null
  onChange: (value: CredentialView) => void
  onDisabled: (value: CredentialView) => void
  onError: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState('')
  const status = credential?.verified
    ? 'подключён'
    : credential?.configured && credential.enabled
      ? 'ошибка ключа'
      : 'не подключён'
  const statusClass = credential?.verified
    ? 'is-ok'
    : credential?.configured && credential.enabled
      ? 'is-error'
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
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!key.trim() || busy) return
    setBusy(true)
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
      await verify(saved)
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
    onError('')
    try {
      await verify(credential)
    } catch (reason) {
      onError(chatProblem(reason))
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
