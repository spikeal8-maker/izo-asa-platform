import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { AuthView } from '../shared/api'
import { Icon } from '../shared/ui/Icon'
import { ChatStartNotice } from './chat/ChatStartNotice'
import { ChatComposer } from './chat/ChatComposer'
import { ChatCredentialPanel } from './chat/ChatCredentialPanel'
import { ChatMessage } from './chat/ChatMessage'
import { ChatMessageEdit, useConversationLayout } from './chat/ChatMessageEdit'
import { ChatSidebar } from './chat/ChatSidebar'
import { leaveChatMedia } from './chat/AttachmentControl'
import { useChatRuntime } from './chat/useChatRuntime'
import { useVisualViewport } from './chat/useVisualViewport'
import './chat.css'
import './chat/ChatRuntime.css'
const desktopQuery = '(min-width: 1120px)'
const sidebarPreference = 'izo-chat-sidebar-expanded'
function initiallyExpanded() {
try { return localStorage.getItem(sidebarPreference) !== 'false' }
catch { return true }
}
export function ChatPage({ auth, theme, onThemeChange, onLogout }: {
auth: AuthView | null | undefined
theme: 'light' | 'dark'
onThemeChange: (value: 'light' | 'dark') => void
onLogout: () => void
}) {
const runtime = useChatRuntime(auth)
const { branches, sidebar, openingThread, error } = runtime
const { currentChatId, busy } = sidebar
const focused = useRef<HTMLElement | null>(null)
const redirectFocus = useCallback((event: PointerEvent) => {
if (!focused.current?.contains(event.target as Node)) focused.current = null
}, [])
const chatScroll = useConversationLayout(auth?.account.id, currentChatId, runtime.messages,
runtime.executionBlocked, branches.saving || openingThread, focused, redirectFocus)
useLayoutEffect(() => {
runtime.beforeGraphChange.current = chatScroll.preparePrepend
return () => { runtime.beforeGraphChange.current = () => {} }
}, [runtime.beforeGraphChange, chatScroll.preparePrepend])
useEffect(() => () => leaveChatMedia(auth?.account.id), [auth?.account.id])
const [desktop, setDesktop] = useState(() => window.matchMedia(desktopQuery).matches)
const [expanded, setExpanded] = useState(initiallyExpanded)
const [drawerOpen, setDrawerOpen] = useState(false)
const [composerVersion, setComposerVersion] = useState(0)
const composerChatId = useRef(currentChatId)
const openPending = useRef(false)
const drawerOpener = useRef<HTMLButtonElement>(null)
useLayoutEffect(() => {
if (!openPending.current) { composerChatId.current = currentChatId; return }
if (openingThread) return
openPending.current = false
if (composerChatId.current === currentChatId) return
composerChatId.current = currentChatId
setComposerVersion(value => value + 1)
}, [currentChatId, openingThread])
useVisualViewport()
useEffect(() => {
const media = window.matchMedia(desktopQuery)
let wasDesktop = media.matches
let focusFrame = 0
const sync = () => {
const moveFocus = wasDesktop && !media.matches && Boolean(document.activeElement?.closest('.chat-sidebar'))
wasDesktop = media.matches
setDesktop(media.matches); setDrawerOpen(false)
if (moveFocus) focusFrame = requestAnimationFrame(() => drawerOpener.current?.focus())
}
sync(); media.addEventListener('change', sync)
return () => { media.removeEventListener('change', sync); cancelAnimationFrame(focusFrame) }
}, [])
useLayoutEffect(() => {
if (desktop || !drawerOpen) return
const background = [document.querySelector<HTMLElement>('.global-header'),
document.querySelector<HTMLElement>('.skip-link')].filter((node): node is HTMLElement => Boolean(node))
const previous = background.map(node => node.inert)
background.forEach(node => { node.inert = true })
return () => background.forEach((node, index) => { node.inert = previous[index] })
}, [desktop, drawerOpen])
const sidebarOpen = desktop ? expanded : drawerOpen
const compact = desktop && !expanded
function setDesktopExpanded(value: boolean) {
setExpanded(value)
try { localStorage.setItem(sidebarPreference, String(value)) } catch { /* UI preference only. */ }
}
function closeDrawer() {
setDrawerOpen(false)
requestAnimationFrame(() => drawerOpener.current?.focus())
}
function newChat() {
if (busy || runtime.pendingAdmission) return
chatScroll.remember()
openPending.current = false
composerChatId.current = null
runtime.newChat()
setComposerVersion(value => value + 1)
if (!desktop) closeDrawer()
}
async function openChat(chat: (typeof sidebar.history)[number]) {
if (busy || runtime.pendingAdmission) return
  chatScroll.remember()
  if (!desktop) closeDrawer()
  openPending.current = true
  if (await runtime.openChat(chat) && openPending.current) {
    openPending.current = false
    composerChatId.current = chat.id
    setComposerVersion(value => value + 1)
  }
}
const empty = runtime.messages.length === 0
const disabled = !auth || !runtime.policy || openingThread || runtime.executionBlocked
const runtimeNote = error && <div className="chat-runtime-note" role="alert">
<Icon name="info" /><span>{error}</span>
</div>
const composer = <ChatComposer key={`${auth?.account.id ?? 'guest'}:${composerVersion}`}
auth={auth} policy={runtime.policy} credentials={runtime.credentials}
catalogError={runtime.catalogError}
busy={busy} stoppable={Boolean(runtime.activeRequestId)} disabled={disabled}
onSend={runtime.send} onStop={() => void runtime.stop()}
onRefreshPolicy={runtime.refreshPolicy} />
return <section
className={`chat-page ${empty ? 'is-empty' : ''} ${sidebarOpen ? 'sidebar-open' : ''} ${compact ? 'sidebar-compact' : ''}`}
onFocusCapture={event => { focused.current = event.target }}
aria-label="Чат ИЗО АСА">
<ChatSidebar
auth={auth} {...sidebar} theme={theme} onThemeChange={onThemeChange} onLogout={onLogout}
compact={compact} drawerOpen={!desktop && drawerOpen} hiddenFromKeyboard={!desktop && !drawerOpen}
onNewChat={newChat} onOpenChat={chat => void openChat(chat)}
onClose={() => desktop ? setDesktopExpanded(false) : closeDrawer()} onExpand={() => setDesktopExpanded(true)}
/>
{!desktop && drawerOpen && <button className="chat-drawer-backdrop" aria-hidden="true" tabIndex={-1}
onClick={closeDrawer} />}
<div className="chat-main" style={{ gridTemplateRows: 'auto minmax(0, 1fr)' }} inert={!desktop && drawerOpen}>
<div className="chat-toolbar" style={{ height: 'auto', minHeight: 'var(--chat-toolbar-height)', flexWrap: 'wrap', paddingLeft: desktop ? 0 : 56 }}>
{!desktop && !drawerOpen && <button ref={drawerOpener} className="chat-icon-button chat-sidebar-open"
aria-label="Открыть панель" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}>
<Icon name="panel" />
</button>}
{auth && <ChatCredentialPanel
auth={auth} credentials={runtime.credentials}
platformAvailable={runtime.policy?.models.some(item => item.provider === 'platform')}
onChange={runtime.setCredential} onDisabled={runtime.credentialDisabled}
onError={runtime.setError} />}
{branches.activeId && <div className="chat-branch-controls chat-message-actions" role="group" tabIndex={-1} aria-label="Ветки разговора"
aria-busy={branches.saving || openingThread} style={{ marginLeft: 'auto', minWidth: 0, maxWidth: '100%' }}>
<select className="secondary" style={{ color: 'inherit', maxWidth: '45vw' }} aria-label="Ветка разговора" value={branches.activeId} disabled={branches.blocked}
onChange={event => void branches.select(event.target.value)}>
{!branches.listed
&& <option value={branches.activeId}>Текущая ветка</option>}
{branches.value?.branches.map(item => <option key={item.id} value={item.id}>Ветка {item.branch_ordinal}</option>)}
</select>
{branches.value?.next_before_branch_ordinal && <button disabled={branches.loading}
onClick={() => void branches.loadMore()}>Ещё ветки</button>}
{branches.pendingAdmission && <button disabled={branches.saving}
onClick={() => void branches.check()}>Проверить отправку</button>}
{branches.error && <span className="chat-attempt-feedback" role="status">{branches.error}</span>}
{!busy && (branches.needsReload || runtime.pendingAdmission || runtime.executionBlocked) && <button disabled={openingThread || branches.saving}
onClick={() => void branches.retry()}>Обновить ветку</button>}
</div>}
</div>
{empty
? <div className="chat-start-state">
<h1>Чем я могу помочь?</h1>
<ChatStartNotice auth={auth} credentials={runtime.credentials} policy={runtime.policy} />
{runtimeNote}
{composer}
</div>
: <>
<div ref={chatScroll.scrollRef} onScroll={chatScroll.onScroll} className="chat-scroll" aria-live="polite"><div className="chat-column">
<div className="chat-turns">
{runtime.olderCursor !== null && <button type="button" className="chat-load-older"
disabled={runtime.loadingOlder || openingThread}
onClick={() => void runtime.loadOlder(chatScroll.preparePrepend)}>
{runtime.loadingOlder ? 'Загружаем…' : 'Загрузить ранние сообщения'}
</button>}
{runtime.messages.map(message =>
message.role === 'user'
? <ChatMessageEdit key={message.id} message={message} auth={auth} beforeLayout={chatScroll.beforeLayout}
control={branches.forMessage(message.id)} />
: <ChatMessage key={message.graph_turn_id ? `${message.graph_turn_id}:${message.role}` : message.id}
message={message} auth={auth} attempts={runtime.attempts.forTurn(message.graph_turn_id)} />)}
{runtimeNote}
</div>
</div></div>
<div className="chat-composer-dock">{composer}</div>
</>}
</div>
</section>
}
