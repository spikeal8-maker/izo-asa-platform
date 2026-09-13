import { useEffect, useState } from 'react'
import { detectHost } from '../platform/host'
import { ApiStatus } from './ApiStatus'
import { SectionPage } from './SectionPage'
import { Link, usePath } from './router'
import { Icon, type IconName } from '../shared/ui/Icon'
import { Studio } from '../features/studio/Studio'
import { ResultPanel } from '../features/studio/ResultPanel'
import { Gallery } from '../features/gallery/Gallery'
import { AssetPage } from '../features/gallery/AssetPage'
import { AccountPage } from '../features/accounts/AccountPage'
import { SecurityPage, securityPages } from '../features/accounts/SecurityPage'
import { AdminPage, AdminLink } from '../features/admin/AdminPage'
import { AccessPage } from '../features/admin/AccessPage'
import { CreditsPage } from '../features/credits/CreditsPage'
import { FeedPage } from '../features/feed/FeedPage'
import { apiRequest, ApiError, type AuthView } from '../shared/api'
import './layout.css'

function initialTheme(): 'light' | 'dark' {
  try { return localStorage.getItem('izo-theme') === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}
const navigation: { href: string; title: string; icon: IconName }[] = [
  { href: '/', title: 'Лента', icon: 'feed' },
  { href: '/image', title: 'Студия', icon: 'spark' },
  { href: '/gallery', title: 'Галерея', icon: 'grid' },
]
const directions = [
  { href: '/studio/chat', title: 'Чат' },
  { href: '/image', title: 'Изображение' },
  { href: '/studio/video', title: 'Видео' },
  { href: '/studio/audio', title: 'Аудио' },
  { href: '/studio/3d', title: '3D' },
]

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
  const direction = directions.find(item => item.href === path)?.href

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
    if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); document.title = `${heading.textContent} · ИЗО АСА` }
  }, [path])

  const activePrimary = (href: string) => href === '/' ? feed : href === '/image' ? studio : gallery || detail
  return <div className="app" data-platform={host}>
    <a className="skip-link" href="#main">К содержимому</a>
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="ИЗО АСА — лента"><span className="brand-mark"><Icon name="spark" /></span><span>ИЗО АСА</span></Link>
      <nav aria-label="Основные разделы">{navigation.map(item => <Link href={item.href} key={item.href}
        aria-label={item.title} className={activePrimary(item.href) ? 'active' : ''}
        aria-current={activePrimary(item.href) ? 'page' : undefined}><Icon name={item.icon} /><span>{item.title}</span></Link>)}</nav>
      <div className="sidebar-bottom">
        <Link href="/account/credits" className="side-link">Баланс</Link>
        <Link href="/account" className="side-link">Аккаунт</Link>
        {(account || credits || admin || auth) && <AdminLink path={path} />}
      </div>
    </aside>

    <div className="app-body"><header className="topbar">
      <div className="mobile-head">
        <button className="mobile-menu-button" aria-label={mobileMenu ? 'Закрыть меню' : 'Открыть меню'} onClick={() => setMobileMenu(value => !value)}>☰</button>
        <Link className="mobile-brand" href="/">ИЗО АСА</Link>
      </div>
      <nav className="direction-nav" aria-label="Инструменты">{directions.map(item => <Link key={item.href} href={item.href}
        className={direction === item.href || (item.href === '/image' && studio) ? 'active' : ''}>{item.title}</Link>)}</nav>
      <div className="header-actions">
        {auth ? <><Link className="balance-button" href="/account/credits">Баланс</Link>
          <Link className="avatar" href="/account" aria-label="Аккаунт">{auth.account.display_name.slice(0, 1).toUpperCase()}</Link></>
          : <><Link className="login-link" href="/login">Войти</Link><Link className="signup-link" href="/register">Регистрация</Link></>}
        <button className="icon-button" aria-label="Переключить тему" onClick={() => setTheme(value => value === 'light' ? 'dark' : 'light')}><Icon name="sun" /></button>
      </div>
      {mobileMenu && <div className="mobile-menu" role="dialog" aria-label="Меню">
        <div className="mobile-menu-directions">{directions.map(item => <Link key={item.href} href={item.href}>{item.title}</Link>)}</div>
        <div className="mobile-menu-account">{auth ? <><Link href="/account">Аккаунт</Link><Link href="/account/credits">Баланс</Link></>
          : <><Link href="/login">Войти</Link><Link href="/register">Создать аккаунт</Link></>}</div>
      </div>}
    </header>

    <div className="content"><main id="main" tabIndex={-1}>
      {accessAdmin ? <AccessPage key={path} /> : admin ? <AdminPage key={path} path={path} /> : credits ? <CreditsPage />
        : security ? <SecurityPage key={path} mode={security} />
        : account ? <AccountPage key={path} mode={path === '/register' ? 'register' : path === '/login' ? 'login' : 'account'} />
        : feed ? <FeedPage /> : studio ? <Studio key={path} /> : gallery ? <Gallery key={path} />
        : detail ? <AssetPage key={path} id={path.slice('/gallery/'.length)} />
        : jobs ? <ResultPanel key={path} id={path === '/jobs' ? undefined : path.slice('/jobs/'.length)} />
        : <SectionPage path={path} />}
    </main><footer><span>ИЗО АСА</span><ApiStatus /></footer></div></div>
  </div>
}
