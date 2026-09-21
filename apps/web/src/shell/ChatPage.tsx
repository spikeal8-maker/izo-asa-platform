import { useEffect, useState } from 'react'
import type { AuthView } from '../shared/api'
import { Icon } from '../shared/ui/Icon'
import { ChatComposer } from './chat/ChatComposer'
import { ChatSidebar } from './chat/ChatSidebar'
import type { LocalChat, LocalTurn } from './chat/types'
import { useVisualViewport } from './chat/useVisualViewport'
import './chat.css'

const runtimeNotice = 'Текстовый помощник пока не подключён к серверу. Выбранные инструменты и вложения здесь не имитируют серверную обработку.'
const desktopQuery = '(min-width: 1120px)'

export function ChatPage({ auth, theme, onThemeChange, onLogout }: {
  auth: AuthView | null | undefined
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
}) {
  const [turns, setTurns] = useState<LocalTurn[]>([])
  const [history, setHistory] = useState<LocalChat[]>([])
  const [currentChatId, setCurrentChatId] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(() => window.matchMedia(desktopQuery).matches)

  useVisualViewport()

  useEffect(() => {
    const media = window.matchMedia(desktopQuery)
    const syncSidebarMode = () => setSidebarOpen(media.matches)
    syncSidebarMode()
    media.addEventListener('change', syncSidebarMode)
    return () => media.removeEventListener('change', syncSidebarMode)
  }, [])

  function newChat() {
    setCurrentChatId(null)
    setTurns([])
    setNotice('')
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  function openChat(chat: LocalChat) {
    setCurrentChatId(chat.id)
    setTurns(chat.turns)
    setNotice(chat.turns.length ? runtimeNotice : '')
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  function send(text: string) {
    const now = Date.now()
    const turn = { id: now, text }
    const nextTurns = [...turns, turn]
    const chatId = currentChatId ?? now
    setTurns(nextTurns)
    setCurrentChatId(chatId)
    setHistory(current => {
      const entry = { id: chatId, title: nextTurns[0]?.text.slice(0, 72) || 'Чат', turns: nextTurns }
      return [entry, ...current.filter(item => item.id !== chatId)]
    })
    setNotice(runtimeNotice)
  }

  const empty = turns.length === 0

  return <section className={`chat-page ${empty ? 'is-empty' : ''} ${sidebarOpen ? 'sidebar-open' : ''}`} aria-label="Чат ИЗО АСА">
    <ChatSidebar
      auth={auth}
      history={history}
      currentChatId={currentChatId}
      theme={theme}
      onThemeChange={onThemeChange}
      onLogout={onLogout}
      onNewChat={newChat}
      onOpenChat={openChat}
      onClose={() => setSidebarOpen(false)}
    />

    {sidebarOpen && <button className="chat-drawer-backdrop" aria-label="Закрыть историю" onClick={() => setSidebarOpen(false)} />}

    <div className="chat-main">
      <div className="chat-toolbar">
        {!sidebarOpen && <button className="chat-icon-button chat-sidebar-open" aria-label="Открыть панель"
          onClick={() => setSidebarOpen(true)}><Icon name="panel" /></button>}
      </div>

      {empty
        ? <div className="chat-start-state">
            <h1>Чем я могу помочь?</h1>
            <ChatComposer auth={auth} onSend={send} />
          </div>
        : <>
            <div className="chat-scroll" aria-live="polite"><div className="chat-column">
              <div className="chat-turns">
                {turns.map(turn => <div className="chat-turn chat-turn-user" key={turn.id}>
                  <div className="chat-user-bubble">{turn.text}</div>
                </div>)}
                {notice && <div className="chat-runtime-note" role="status"><Icon name="info" /><span>{notice}</span></div>}
              </div>
            </div></div>
            <div className="chat-composer-dock">
              <ChatComposer auth={auth} onSend={send} />
            </div>
          </>}
    </div>
  </section>
}
