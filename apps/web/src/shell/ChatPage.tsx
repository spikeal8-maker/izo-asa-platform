import { useEffect, useState } from 'react'
import type { AuthView } from '../shared/api'
import { Icon } from '../shared/ui/Icon'
import { Link } from './router'
import { ChatComposer } from './chat/ChatComposer'
import { ChatCredentialPanel } from './chat/ChatCredentialPanel'
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
    if (!auth) return
    const key = `izo-chat-current:${auth.account.id}`
    if (runtime.currentChatId) {
      sessionStorage.setItem(key, runtime.currentChatId)
      return
    }
    if (!runtime.history.length || runtime.busy) return
    const remembered = sessionStorage.getItem(key)
    const chat = runtime.history.find(item => item.id === remembered)
    if (chat) void runtime.openChat(chat)
  }, [auth?.account.id, runtime.currentChatId, runtime.history, runtime.busy])

  useEffect(() => {
    const media = window.matchMedia(desktopQuery)
    const sync = () => setSidebarOpen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  function newChat() {
    if (auth) sessionStorage.removeItem(`izo-chat-current:${auth.account.id}`)
    runtime.newChat()
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  async function openChat(chat: (typeof runtime.history)[number]) {
    await runtime.openChat(chat)
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  const empty = runtime.messages.length === 0
  const disabled = !auth || !runtime.policy || !runtime.modelCredential?.verified
  const composer = <ChatComposer
    policy={runtime.policy}
    credentials={runtime.credentials}
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
          credentials={runtime.credentials}
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
                : !runtime.modelCredential?.verified
                  ? <p className="chat-start-note">Подключите и проверьте API key выбранного провайдера.</p>
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
