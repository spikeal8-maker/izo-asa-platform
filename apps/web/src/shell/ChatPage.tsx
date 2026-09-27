import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
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
const [desktop, setDesktop] = useState(() => window.matchMedia(desktopQuery).matches)
const [expanded, setExpanded] = useState(initiallyExpanded)
const [drawerOpen, setDrawerOpen] = useState(false)
const drawerOpener = useRef<HTMLButtonElement>(null)
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
function closeSidebar() { if (desktop) setDesktopExpanded(false); else closeDrawer() }
function newChat() {
runtime.newChat()
if (!desktop) closeDrawer()
}
async function openChat(chat: (typeof runtime.history)[number]) {
if (!desktop) closeDrawer()
await runtime.openChat(chat)
}
const empty = runtime.messages.length === 0
const disabled = !auth || !runtime.policy || !runtime.credential?.verified
const composer = <ChatComposer
auth={auth} policy={runtime.policy}
busy={runtime.busy} stoppable={Boolean(runtime.activeRequestId)} disabled={disabled}
onSend={runtime.send} onStop={() => void runtime.stop()}
onUnsupported={() => runtime.setError('Этот инструмент ещё не подключён к текстовому Chat D1.')} />
return <section
className={`chat-page ${empty ? 'is-empty' : ''} ${sidebarOpen ? 'sidebar-open' : ''} ${compact ? 'sidebar-compact' : ''}`}
aria-label="Чат ИЗО АСА">
<ChatSidebar
auth={auth} history={runtime.history} currentChatId={runtime.currentChatId}
busy={runtime.busy} theme={theme} onThemeChange={onThemeChange} onLogout={onLogout}
compact={compact} drawerOpen={!desktop && drawerOpen} hiddenFromKeyboard={!desktop && !drawerOpen}
onNewChat={newChat} onOpenChat={chat => void openChat(chat)}
onClose={closeSidebar} onExpand={() => setDesktopExpanded(true)}
/>
{!desktop && drawerOpen && <button className="chat-drawer-backdrop" aria-hidden="true" tabIndex={-1}
onClick={closeDrawer} />}
<div className="chat-main" inert={!desktop && drawerOpen}>
<div className="chat-toolbar">
{!desktop && !drawerOpen && <button ref={drawerOpener} className="chat-icon-button chat-sidebar-open"
aria-label="Открыть панель" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}>
<Icon name="panel" />
</button>}
{auth && <ChatCredentialPanel
auth={auth} credential={runtime.credential}
onChange={runtime.setCredential} onDisabled={runtime.credentialDisabled}
onError={runtime.setError} />}
</div>
{empty
? <div className="chat-start-state">
<h1>Чем я могу помочь?</h1>
{auth === undefined
? <p className="chat-start-note" role="status">Проверяем вход…</p>
: !auth
? <p className="chat-start-note">Для сохранённого разговора нужен аккаунт. <Link href="/login">Войти</Link></p>
: !runtime.credential?.verified
? <p className="chat-start-note">Подключите и проверьте свой ключ DeepSeek.</p>
: null}
{runtime.error && <div className="chat-runtime-note" role="alert">
<Icon name="info" /><span>{runtime.error}</span>
</div>}
{composer}
</div>
: <>
<div className="chat-scroll" aria-live="polite"><div className="chat-column">
<div className="chat-turns">
{runtime.messages.map(message =>
<ChatMessage key={message.id} message={message} />)}
{runtime.error && <div className="chat-runtime-note" role="alert">
<Icon name="info" /><span>{runtime.error}</span>
</div>}
</div>
</div></div>
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
const [open, setOpen] = useState(!credential?.verified)
const [busy, setBusy] = useState(false)
const [key, setKey] = useState('')
useEffect(() => {
setOpen(!credential?.verified)
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
