import type { AuthView } from '../shared/api'
import { Icon, type IconName } from '../shared/ui/Icon'
import { AdminLink } from '../features/admin/AdminPage'
import { Link } from './router'

const directions = [
  { href: '/studio/chat', title: 'Чат' },
  { href: '/image', title: 'Изображение' },
  { href: '/studio/video', title: 'Видео' },
  { href: '/studio/audio', title: 'Аудио' },
  { href: '/studio/3d', title: '3D' },
]
const primaryItems: { href: string; title: string; icon: IconName }[] = [
  { href: '/', title: 'Лента', icon: 'feed' },
  { href: '/image', title: 'Студия', icon: 'spark' },
  { href: '/gallery', title: 'Галерея', icon: 'grid' },
]

function mobileContext(path: string) {
  if (path === '/' || path === '/feed') return 'Лента'
  if (path === '/gallery' || path.startsWith('/gallery/')) return 'Галерея'
  if (path === '/image' || path === '/studio/image') return 'Изображение'
  const direction = directions.find(item => item.href === path)
  if (direction) return direction.title
  if (path.startsWith('/admin')) return 'Админка'
  if (path.startsWith('/account') || path === '/login' || path === '/register') return 'Аккаунт'
  if (path.startsWith('/jobs')) return 'Задание'
  return 'ИЗО АСА'
}

export function PrimarySidebar({ path, auth }: { path: string; auth: AuthView | null | undefined }) {
  const feed = path === '/' || path === '/feed'
  const studio = ['/image', '/studio/image'].includes(path)
  const gallery = path === '/gallery' || path.startsWith('/gallery/')
  const active = (href: string) => href === '/' ? feed : href === '/image' ? studio : gallery
  return <aside className="sidebar">
    <Link href="/" className="brand" aria-label="ИЗО АСА — лента">
      <span className="brand-mark"><Icon name="spark" /></span><span>ИЗО АСА</span>
    </Link>
    <nav aria-label="Основные разделы">{primaryItems.map(item => <Link href={item.href} key={item.href}
      aria-label={item.title} className={active(item.href) ? 'active' : ''}
      aria-current={active(item.href) ? 'page' : undefined}><Icon name={item.icon} /><span>{item.title}</span></Link>)}</nav>
    <div className="sidebar-bottom">
      <Link href="/account/credits" className="side-link">Баланс</Link>
      <Link href="/account" className="side-link">Аккаунт</Link>
      {auth && <AdminLink path={path} />}
    </div>
  </aside>
}

export function TopBar({ path, auth, theme, mobileMenu, onToggleMenu, onToggleTheme }: {
  path: string
  auth: AuthView | null | undefined
  theme: 'light' | 'dark'
  mobileMenu: boolean
  onToggleMenu: () => void
  onToggleTheme: () => void
}) {
  const studio = ['/image', '/studio/image'].includes(path)
  const direction = directions.find(item => item.href === path)?.href
  return <header className="topbar">
    <div className="mobile-head">
      <button className="mobile-menu-button" aria-label="Меню" aria-expanded={mobileMenu}
        aria-controls="mobile-menu" onClick={onToggleMenu}>☰</button>
      <Link className="mobile-brand" href="/">ИЗО АСА</Link>
      <span className="mobile-context" aria-current="page">{mobileContext(path)}</span>
    </div>
    <nav className="direction-nav" aria-label="Инструменты">{directions.map(item => <Link key={item.href} href={item.href}
      className={direction === item.href || (item.href === '/image' && studio) ? 'active' : ''}>{item.title}</Link>)}</nav>
    <div className="header-actions">
      {auth ? <><Link className="balance-button" href="/account/credits">Баланс</Link>
        <Link className="avatar" href="/account" aria-label="Аккаунт">{auth.account.display_name.slice(0, 1).toUpperCase()}</Link></>
        : <><Link className="login-link" href="/login">Войти</Link><Link className="signup-link" href="/register">Регистрация</Link></>}
      <button className="icon-button" aria-label="Переключить тему" data-theme-value={theme} onClick={onToggleTheme}><Icon name="sun" /></button>
    </div>
    {mobileMenu && <div id="mobile-menu" className="mobile-menu" role="dialog" aria-label="Меню">
      <div className="mobile-menu-directions">{directions.map(item => <Link key={item.href} href={item.href}>{item.title}</Link>)}</div>
      <div className="mobile-menu-account">{auth ? <><Link href="/account">Аккаунт</Link><Link href="/account/credits">Баланс</Link></>
        : <><Link href="/login">Войти</Link><Link href="/register">Создать аккаунт</Link></>}</div>
    </div>}
  </header>
}
