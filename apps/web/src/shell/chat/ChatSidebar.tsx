import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { AuthView, ThreadView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { AccountMenu } from '../TopBar'
import { ThreadRenameForm, useThreadRenameEditor } from './ThreadRenameForm'
import { useThreadSearchView, type ThreadSearch } from './useThreadSearch'
import './ChatSidebar.css'

export function ChatSidebar({ auth, history, historyCursor, loadingHistory, onLoadMoreHistory, search,
  currentChatId, busy, renamingThreadId, onRenameChat, theme, onThemeChange, onLogout,
  compact, drawerOpen, hiddenFromKeyboard, onNewChat, onOpenChat, onClose, onExpand }: {
  auth: AuthView | null | undefined
  history: ThreadView[]
  historyCursor: string | null
  loadingHistory: boolean
  onLoadMoreHistory: () => void
  search: ThreadSearch
  currentChatId: string | null
  busy: boolean
  renamingThreadId: string | null
  onRenameChat: (id: string, title: string) => Promise<boolean>
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
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)
  const profileButtonRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const { editingId, historyList, openRename, closeRename } = useThreadRenameEditor(
    hiddenFromKeyboard || compact, renamingThreadId, closeButtonRef)
  const { searchButton, searchInput, changeSearch, historyScroll, focusedRow } = useThreadSearchView(
    search, editingId, historyList, closeRename)

  useEffect(() => {
    if (!hiddenFromKeyboard && !compact) return
    setSearchOpen(false)
    search.setQuery('')
    setProfileOpen(false)
  }, [hiddenFromKeyboard, compact, search.setQuery])

  useLayoutEffect(() => {
    if (drawerOpen) closeButtonRef.current?.focus({ preventScroll: true })
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

  const visibleHistory = search.active ? search.rows : history
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
            <input ref={searchInput} autoFocus value={search.query} onChange={event => changeSearch(event.target.value)}
              aria-label="Поиск по чатам" placeholder="Поиск по чатам"
              aria-invalid={search.invalid || undefined} aria-describedby={search.error ? 'chat-search-error' : undefined}
              onKeyDown={event => {
                if (event.key === 'Escape') {
                  event.preventDefault(); event.stopPropagation()
                  setSearchOpen(false)
                  changeSearch('')
                  searchButton.current?.focus({ preventScroll: true })
                }
              }} />
          </label>
        : <span className="chat-sidebar-title">История</span>}
      <div className="chat-sidebar-head-actions">
        <button ref={closeButtonRef} className="chat-icon-button"
          aria-label={compact ? 'Развернуть панель' : 'Скрыть панель'}
          onClick={() => { setSearchOpen(false); setProfileOpen(false); compact ? onExpand() : onClose() }}>
          <Icon name="panel" /></button>
        <button ref={searchButton} className="chat-icon-button" aria-label="Поиск чатов" aria-expanded={searchOpen}
          onClick={() => { if (compact) onExpand(); setSearchOpen(value => compact || !value); if (searchOpen) changeSearch('') }}><Icon name="search" /></button>
      </div>
    </div>

    <div className="chat-sidebar-actions">
      <button aria-label="Новый чат" onClick={onNewChat} disabled={busy}><Icon name="edit" /><span>Новый чат</span></button>
    </div>

    {!compact && <><div className="chat-side-section">Чаты</div>
    <div ref={historyList} className="chat-history-list" aria-label="Список чатов"
      onScroll={event => { if (!search.active) historyScroll.current = event.currentTarget.scrollTop }}
      onFocusCapture={event => { focusedRow.current = event.target }}>
      {search.active && !search.error && <div className="chat-side-section" role="status" aria-label="Результаты поиска">
        {search.loading ? 'Ищем чаты…' : !search.rows.length ? 'Чаты не найдены'
          : `${search.cursor ? 'Показано' : 'Найдено'}: ${search.rows.length}`}</div>}
      {search.active && search.error && <><p id="chat-search-error" role="alert">{search.error}</p>
        {!search.invalid && <button className="chat-history-more" onClick={search.retry}>Повторить поиск</button>}</>}
      {visibleHistory.map(chat => <div className="chat-history-row" key={chat.id}>
        <button className={chat.id === currentChatId ? 'chat-history-item active' : 'chat-history-item'}
          id={`chat-history-${chat.id}`} onClick={() => onOpenChat(chat)} disabled={busy}
          title={chat.title}>{chat.title}</button>
        <button className="chat-icon-button chat-history-rename" aria-label="Переименовать"
          aria-describedby={`chat-history-${chat.id}`} title="Переименовать"
          aria-expanded={editingId === chat.id} disabled={!auth || !!editingId || !!renamingThreadId}
          onClick={event => openRename(chat.id, event.currentTarget)}>
          <Icon name="edit" /></button>
        {editingId === chat.id && <ThreadRenameForm title={chat.title}
          onSave={title => onRenameChat(chat.id, title)} onClose={closeRename} />}
      </div>)}
      {(search.active ? search.cursor && !search.error : historyCursor) && <button className="chat-history-more"
        onClick={search.active ? search.loadMore : onLoadMoreHistory} disabled={search.active ? search.loading : loadingHistory}
        aria-label={search.active ? 'Загрузить ещё результаты' : 'Загрузить ранние чаты'}>
        {(search.active ? search.loading : loadingHistory) ? 'Загружаем…'
          : search.active ? 'Загрузить ещё результаты' : 'Загрузить ранние чаты'}</button>}
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
