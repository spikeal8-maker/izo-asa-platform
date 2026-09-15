import type { AuthView } from '../shared/api'
import { Icon, type IconName } from '../shared/ui/Icon'
import { AdminLink } from '../features/admin/AdminPage'
import { Link } from './router'
import './product-nav.css'

const directions: { href: string; title: string; icon: IconName }[] = [
  { href: '/', title: 'Чат', icon: 'chat' },
  { href: '/image', title: 'Изображение', icon: 'image' },
  { href: '/studio/video', title: 'Видео', icon: 'video' },
  { href: '/studio/audio', title: 'Звук', icon: 'audio' },
  { href: '/studio/3d', title: '3D', icon: 'cube' },
]
const primaryItems: { href: string; title: string; icon: IconName }[] = [
  { href: '/', title: 'Чат', icon: 'chat' },
  { href: '/feed', title: 'Лента', icon: 'feed' },
  { href: '/gallery', title: 'Галерея', icon: 'grid' },
]

function mobileContext(path: string) {
  if (path === '/' || path === '/studio/chat') return 'Чат'
  if (path === '/feed') return 'Лента'
  if (path === '/gallery' || path.startsWith('/gallery/')) return 'Галерея'
  if (path === '/image' || path === '/studio/image') return 'Изображение'
  const direction = directions.find(item => item.href === path)
  if (direction) return direction.title
  if (path.startsWith('/admin')) return 'Админка'
  if (path.startsWith('/account') || path === '/login' || path === '/register') return 'Аккаунт'
  if (path.startsWith('/jobs')) return 'Задание'
  if (path === '/help') return 'Помощь'
  return 'ИЗО АСА'
}

export function PrimarySidebar({ path, auth }: { path: string; auth: AuthView | null | undefined }) {
  const active = (href: string) => href === '/'
    ? path === '/' || path === '/studio/chat'
    : href === '/gallery' ? path === '/gallery' || path.startsWith('/gallery/') : path === href
  return <aside className="sidebar">
    <Link href="/" className="brand" aria-label="ИЗО АСА — чат">
      <span className="brand-mark"><Icon name="spark" /></span><span>ИЗО АСА</span>
    </Link>
    <nav aria-label="Основные разделы">{primaryItems.map(item => <Link href={item.href} key={item.href}
      aria-label={item.title} className={active(item.href) ? 'active' : ''}
      aria-current={active(item.href) ? 'page' : undefined}><Icon name={item.icon} /><span>{item.title}</span></Link>)}</nav>
    <div className="sidebar-bottom">
      <Link href="/help" className="side-link"><Icon name="info" />Помощь</Link>
      <Link href="/account/credits" className="side-link">Токены</Link>
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
  const chat = path === '/' || path === '/studio/chat'
  const studioImage = ['/image', '/studio/image'].includes(path)
  const activeDirection = (href: string) => href === '/' ? chat : href === '/image' ? studioImage : path === href
  return <header className="topbar">
    <div className="mobile-head">
      <button className="mobile-menu-button" aria-label="Меню" aria-expanded={mobileMenu}
        aria-controls="mobile-menu" onClick={onToggleMenu}>☰</button>
      <Link className="mobile-brand" href="/">ИЗО АСА</Link>
      <span className="mobile-context" aria-current="page">{mobileContext(path)}</span>
    </div>
    <div className="model-chip" aria-label="Модель: ASA Auto"><span>ASA Auto</span><small>Auto</small></div>
    <nav className="direction-nav" aria-label="Творческие инструменты ИЗО АСА">{directions.map(item => <Link key={item.href} href={item.href}
      aria-label={item.title} className={activeDirection(item.href) ? 'active' : ''}
      aria-current={activeDirection(item.href) ? 'page' : undefined}>
      <Icon name={item.icon} /><span>{item.title}</span></Link>)}</nav>
    <div className="header-actions">
      <Link className="top-utility" href="/feed"><Icon name="feed" /><span>Лента</span></Link>
      <Link className="top-utility" href="/gallery"><Icon name="grid" /><span>Галерея</span></Link>
      <Link className="top-utility" href="/help"><Icon name="info" /><span>Помощь</span></Link>
      {auth ? <><Link className="balance-button" href="/account/credits">Токены</Link>
        <Link className="avatar" href="/account" aria-label="Аккаунт">{auth.account.display_name.slice(0, 1).toUpperCase()}</Link></>
        : <><Link className="login-link" href="/login">Войти</Link><Link className="signup-link" href="/register">Регистрация</Link></>}
      <button className="icon-button" aria-label="Переключить тему" data-theme-value={theme} onClick={onToggleTheme}><Icon name="sun" /></button>
    </div>
    {mobileMenu && <div id="mobile-menu" className="mobile-menu" role="dialog" aria-label="Меню">
      <div className="mobile-menu-primary"><Link href="/feed">Лента</Link><Link href="/gallery">Галерея</Link><Link href="/help">Помощь</Link></div>
      <div className="mobile-menu-account">{auth ? <><Link href="/account">Аккаунт</Link><Link href="/account/credits">Токены</Link></>
        : <><Link href="/login">Войти</Link><Link href="/register">Создать аккаунт</Link></>}</div>
    </div>}
  </header>
}
