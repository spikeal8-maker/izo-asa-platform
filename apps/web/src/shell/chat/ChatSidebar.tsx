import { useEffect, useRef, useState } from 'react'
import type { AuthView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { AccountMenu } from '../TopBar'
import type { LocalChat } from './types'
import './ChatSidebar.css'

export function ChatSidebar({ auth, history, currentChatId, theme, onThemeChange, onLogout, onNewChat, onOpenChat, onClose }: {
  auth: AuthView | null | undefined
  history: LocalChat[]
  currentChatId: number | null
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
  onNewChat: () => void
  onOpenChat: (chat: LocalChat) => void
  onClose: () => void
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)
  const profileButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const dismiss = (event: PointerEvent) => {
      const target = event.target
      if (profileOpen && target instanceof Node && !profileRef.current?.contains(target)) setProfileOpen(false)
    }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [profileOpen])

  useEffect(() => {
    if (!profileOpen) return
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setProfileOpen(false)
      requestAnimationFrame(() => profileButtonRef.current?.focus())
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [profileOpen])

  const normalizedSearch = searchQuery.trim().toLocaleLowerCase('ru-RU')
  const visibleHistory = normalizedSearch
    ? history.filter(chat => chat.title.toLocaleLowerCase('ru-RU').includes(normalizedSearch))
    : history
  const initial = auth?.account.display_name.trim().slice(0, 1).toUpperCase() || ''

  return <aside className="chat-sidebar" aria-label="История чатов">
    <div className="chat-sidebar-head">
      {searchOpen
        ? <label className="chat-search-box chat-search-head"><Icon name="search" />
            <input autoFocus value={searchQuery} onChange={event => setSearchQuery(event.target.value)}
              aria-label="Поиск по чатам" placeholder="Поиск по чатам"
              onKeyDown={event => {
                if (event.key === 'Escape') {
                  setSearchOpen(false)
                  setSearchQuery('')
                }
              }} />
          </label>
        : <span className="chat-sidebar-title">История</span>}
      <div className="chat-sidebar-head-actions">
        <button className="chat-icon-button" aria-label="Поиск чатов" aria-expanded={searchOpen}
          onClick={() => { setSearchOpen(value => !value); if (searchOpen) setSearchQuery('') }}><Icon name="search" /></button>
        <button className="chat-icon-button" aria-label="Скрыть панель" onClick={onClose}><Icon name="panel" /></button>
      </div>
    </div>

    <div className="chat-sidebar-actions">
      <button onClick={onNewChat}><Icon name="edit" /><span>Новый чат</span></button>
    </div>

    <div className="chat-side-section">Чаты</div>
    <div className="chat-history-list" aria-label="Список чатов">
      {visibleHistory.map(chat => <button className={chat.id === currentChatId ? 'chat-history-item active' : 'chat-history-item'}
        key={chat.id} onClick={() => onOpenChat(chat)} title={chat.title}>{chat.title}</button>)}
    </div>

    {auth && <div className="chat-sidebar-bottom">
      <div className="chat-side-profile" ref={profileRef}
        onKeyDown={event => {
          if (event.key !== 'Escape' || !profileOpen) return
          event.preventDefault()
          setProfileOpen(false)
          requestAnimationFrame(() => profileButtonRef.current?.focus())
        }}>
        <button ref={profileButtonRef} className="chat-profile-button" aria-label="Профиль в боковой панели" aria-expanded={profileOpen}
          onClick={() => setProfileOpen(value => !value)}>
          <span className="chat-profile-avatar">{initial}</span>
          <span className="chat-profile-copy"><span className="chat-profile-name">{auth.account.display_name}</span><span className="chat-profile-plan">ИЗО АСА</span></span>
          <Icon name="more" />
        </button>
        {profileOpen && <AccountMenu className="chat-profile-menu" theme={theme} onThemeChange={onThemeChange}
          onLogout={onLogout} onClose={() => setProfileOpen(false)}
          onEscape={() => { setProfileOpen(false); requestAnimationFrame(() => profileButtonRef.current?.focus()) }} />}
      </div>
    </div>}
  </aside>
}
