import { useEffect, useRef, useState } from 'react'
import type { AuthView, ThreadView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { AccountMenu } from '../TopBar'
import './ChatSidebar.css'

export function ChatSidebar({ auth, history, historyCursor, loadingHistory, onLoadMoreHistory,
  currentChatId, busy, theme, onThemeChange, onLogout,
  compact, drawerOpen, hiddenFromKeyboard, onNewChat, onOpenChat, onClose, onExpand }: {
  auth: AuthView | null | undefined
  history: ThreadView[]
  historyCursor: string | null
  loadingHistory: boolean
  onLoadMoreHistory: () => void
  currentChatId: string | null
  busy: boolean
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
  compact: boolean
  drawerOpen: boolean
  hiddenFromKeyboard: boolean
  onNewChat: () => void
  onOpenChat: (chat: ThreadView) => void
  onClose: () => void
  onExpand: () => void
}) {
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)
  const profileButtonRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!hiddenFromKeyboard) return
    setSearchOpen(false)
    setSearchQuery('')
    setProfileOpen(false)
  }, [hiddenFromKeyboard])

  useEffect(() => {
    if (!drawerOpen) return
    const frame = requestAnimationFrame(() => closeButtonRef.current?.focus())
    return () => cancelAnimationFrame(frame)
  }, [drawerOpen])

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

  return <aside ref={sidebarRef} className={`chat-sidebar ${compact ? 'is-compact' : ''}`}
    role={drawerOpen ? 'dialog' : undefined} aria-modal={drawerOpen || undefined}
    aria-label="История чатов" aria-hidden={hiddenFromKeyboard} inert={hiddenFromKeyboard}
    onKeyDown={event => {
      if (!drawerOpen) return
      if (event.key === 'Escape' && !searchOpen && !profileOpen) {
        event.preventDefault(); onClose(); return
      }
      if (event.key !== 'Tab') return
      const elements = [...(sidebarRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled),input:not(:disabled),a[href]') ?? [])]
        .filter(item => item.getClientRects().length > 0)
      if (!elements.length) return
      if (event.shiftKey && document.activeElement === elements[0]) {
        event.preventDefault(); elements.at(-1)?.focus()
      } else if (!event.shiftKey && document.activeElement === elements.at(-1)) {
        event.preventDefault(); elements[0].focus()
      }
    }}>
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
        <button ref={closeButtonRef} className="chat-icon-button"
          aria-label={compact ? 'Развернуть панель' : 'Скрыть панель'}
          onClick={() => { setSearchOpen(false); setProfileOpen(false); compact ? onExpand() : onClose() }}>
          <Icon name="panel" /></button>
        <button className="chat-icon-button" aria-label="Поиск чатов" aria-expanded={searchOpen}
          onClick={() => { if (compact) onExpand(); setSearchOpen(value => compact || !value); if (searchOpen) setSearchQuery('') }}><Icon name="search" /></button>
      </div>
    </div>

    <div className="chat-sidebar-actions">
      <button aria-label="Новый чат" onClick={onNewChat} disabled={busy}><Icon name="edit" /><span>Новый чат</span></button>
    </div>

    {!compact && <><div className="chat-side-section">Чаты</div>
    <div className="chat-history-list" aria-label="Список чатов">
      {visibleHistory.map(chat => <button className={chat.id === currentChatId ? 'chat-history-item active' : 'chat-history-item'}
        key={chat.id} onClick={() => onOpenChat(chat)} disabled={busy}
        title={chat.title}>{chat.title}</button>)}
      {historyCursor && <button className="chat-history-more" onClick={onLoadMoreHistory}
        disabled={loadingHistory} aria-label="Загрузить ранние чаты">
        {loadingHistory ? 'Загружаем…' : 'Загрузить ранние чаты'}</button>}
    </div></>}

    {auth && <div className="chat-sidebar-bottom">
      <div className="chat-side-profile" ref={profileRef}
        onKeyDown={event => {
          if (event.key !== 'Escape' || !profileOpen) return
          event.preventDefault()
          setProfileOpen(false)
          requestAnimationFrame(() => profileButtonRef.current?.focus())
        }}>
        <button ref={profileButtonRef} className="chat-profile-button" aria-label="Профиль в боковой панели" aria-expanded={profileOpen}
          onClick={() => { if (compact) onExpand(); setProfileOpen(value => !value) }}>
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
