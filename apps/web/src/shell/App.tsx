import { useEffect, useState } from 'react'
import { detectHost } from '../platform/host'
import { SectionPage } from './SectionPage'
import { usePath } from './router'
import { Studio } from '../features/studio/Studio'
import { ResultPanel } from '../features/studio/ResultPanel'
import { Gallery } from '../features/gallery/Gallery'
import { AssetPage } from '../features/gallery/AssetPage'
import { AccountPage } from '../features/accounts/AccountPage'
import { SecurityPage, securityPages } from '../features/accounts/SecurityPage'
import { AdminPage } from '../features/admin/AdminPage'
import { AccessPage } from '../features/admin/AccessPage'
import { CreditsPage } from '../features/credits/CreditsPage'
import { FeedPage } from '../features/feed/FeedPage'
import { apiRequest, ApiError, type AuthView } from '../shared/api'
import { PrimarySidebar } from './PrimarySidebar'
import { TopBar } from './TopBar'
import './layout.css'

function initialTheme(): 'light' | 'dark' {
  try { return localStorage.getItem('izo-theme') === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}

export function App() {
  const [theme, setTheme] = useState(initialTheme)
  const [mobileMenu, setMobileMenu] = useState(false)
  const [auth, setAuth] = useState<AuthView | null | undefined>(undefined)
  const path = usePath()
  const host = detectHost(window)
  const feed = path === '/' || path === '/feed'
  const studio = ['/image', '/studio/image'].includes(path)
  const gallery = path === '/gallery'
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
    const controller = new AbortController()
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal })
      .then(setAuth).catch(reason => {
        if (controller.signal.aborted) return
        if (reason instanceof ApiError && reason.status === 401) setAuth(null)
        else setAuth(null)
      })
    return () => controller.abort()
  }, [path])

  useEffect(() => {
    setMobileMenu(false)
    const heading = document.querySelector<HTMLElement>('main h1')
    if (heading) {
      heading.tabIndex = -1
      heading.focus({ preventScroll: true })
      document.title = `${heading.textContent} · ИЗО АСА`
    }
  }, [path])

  return <div className="app" data-platform={host}>
    <a className="skip-link" href="#main">К содержимому</a>
    <PrimarySidebar path={path} auth={auth} />
    <div className="app-body">
      <TopBar path={path} auth={auth} theme={theme} mobileMenu={mobileMenu}
        onToggleMenu={() => setMobileMenu(value => !value)}
        onToggleTheme={() => setTheme(value => value === 'light' ? 'dark' : 'light')} />
      <div className="content"><main id="main" tabIndex={-1}>
        {accessAdmin ? <AccessPage key={path} /> : admin ? <AdminPage key={path} path={path} /> : credits ? <CreditsPage />
          : security ? <SecurityPage key={path} mode={security} />
          : account ? <AccountPage key={path} mode={path === '/register' ? 'register' : path === '/login' ? 'login' : 'account'} />
          : feed ? <FeedPage /> : studio ? <Studio key={path} /> : gallery ? <Gallery key={path} />
          : detail ? <AssetPage key={path} id={path.slice('/gallery/'.length)} />
          : jobs ? <ResultPanel key={path} id={path === '/jobs' ? undefined : path.slice('/jobs/'.length)} />
          : <SectionPage path={path} />}
      </main><footer><span>ИЗО АСА</span></footer></div>
    </div>
  </div>
}
