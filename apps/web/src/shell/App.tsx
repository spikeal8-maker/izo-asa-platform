import { useEffect, useState } from 'react'
import { detectHost } from '../platform/host'
import { SectionPage } from './SectionPage'
import { canonicalRoute } from './navigation'
import { usePath } from './router'
import { ChatPage } from './ChatPage'
import { Studio } from '../features/studio/Studio'
import { ResultPanel } from '../features/studio/ResultPanel'
import { Gallery } from '../features/gallery/Gallery'
import { AssetPage } from '../features/gallery/AssetPage'
import { AccountPage } from '../features/accounts/AccountPage'
import { SecurityPage, securityPages } from '../features/accounts/SecurityPage'
import { AdminLink, AdminPage } from '../features/admin/AdminPage'
import { AccessPage } from '../features/admin/AccessPage'
import { CreditsPage } from '../features/credits/CreditsPage'
import { FeedPage } from '../features/feed/FeedPage'
import { apiRequest, ApiError, type AuthView } from '../shared/api'
import { TopBar } from './TopBar'
import './layout.css'

function initialTheme(): 'light' | 'dark' {
  try { return localStorage.getItem('izo-theme') === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}

export function App() {
  const [theme, setTheme] = useState(initialTheme)
  const [auth, setAuth] = useState<AuthView | null | undefined>(undefined)
  const rawPath = usePath()
  const path = canonicalRoute(rawPath)
  const host = detectHost(window)
  const chat = path === '/'
  const feed = path === '/feed'
  const studio = path === '/image'
  const gallery = path === '/gallery'
  const section = ['/video', '/audio', '/3d', '/help'].includes(path)
  const security = securityPages[path]
  const account = !!security || ['/account', '/account/sessions', '/login', '/register'].includes(path)
  const credits = path === '/account/credits'
  const admin = path === '/admin' || path.startsWith('/admin/')
  const accessAdmin = path === '/admin/access'
  const detail = path.startsWith('/gallery/')
  const jobs = path === '/jobs' || path.startsWith('/jobs/')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('izo-theme', theme) } catch { /* Optional preference only. */ }
  }, [theme])

  useEffect(() => {
    if (rawPath === path) return
    window.history.replaceState(null, '', path)
    window.dispatchEvent(new Event('izo:navigate'))
  }, [rawPath, path])

  useEffect(() => {
    const controller = new AbortController()
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal })
      .then(setAuth).catch(reason => {
        if (controller.signal.aborted) return
        if (reason instanceof ApiError && reason.status === 401) setAuth(null)
        else setAuth(null)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('main h1')
    if (heading) {
      heading.tabIndex = -1
      heading.focus({ preventScroll: true })
      document.title = `${heading.textContent} · ИЗО АСА`
    } else if (chat) document.title = 'Чат · ИЗО АСА'
  }, [path, chat])

  async function logout() {
    if (!auth) return
    try { await apiRequest<void>('/api/v1/auth/logout', { method: 'POST', csrf: auth.csrf_token }) }
    finally {
      setAuth(null)
      window.history.pushState(null, '', '/')
      window.dispatchEvent(new Event('izo:navigate'))
    }
  }

  return <div className={`app ${chat ? 'chat-shell' : ''}`} data-platform={host}>
    <a className="skip-link" href="#main">К содержимому</a>
    <TopBar path={path} auth={auth} theme={theme} onThemeChange={setTheme} onLogout={() => void logout()} />
    <div className={chat ? 'content chat-content' : 'content'}>
      {admin && <aside className="staff-context" aria-label="Административный доступ"><AdminLink path={path} /></aside>}
      <main id="main" tabIndex={-1}>
      {accessAdmin ? <AccessPage key={path} /> : admin ? <AdminPage key={path} path={path} /> : credits ? <CreditsPage />
        : security ? <SecurityPage key={path} mode={security} />
        : account ? <AccountPage key={path} mode={path === '/register' ? 'register' : path === '/login' ? 'login' : 'account'} />
        : chat ? <ChatPage auth={auth} theme={theme} onThemeChange={setTheme} onLogout={() => void logout()} />
        : feed ? <FeedPage /> : studio ? <Studio key={path} /> : gallery ? <Gallery key={path} />
        : detail ? <AssetPage key={path} id={path.slice('/gallery/'.length)} />
        : jobs ? <ResultPanel key={path} id={path === '/jobs' ? undefined : path.slice('/jobs/'.length)} />
        : section ? <SectionPage path={path} /> : <SectionPage path={path} />}
    </main>{!chat && <footer><span>ИЗО АСА</span></footer>}</div>
  </div>
}
