import type { AuthView } from '../shared/api'
import { Icon } from '../shared/ui/Icon'
import { Link } from './router'

const directions = [
  { href: '/studio/chat', title: 'Чат' },
  { href: '/image', title: 'Изображение' },
  { href: '/studio/video', title: 'Видео' },
  { href: '/studio/audio', title: 'Аудио' },
  { href: '/studio/3d', title: '3D' },
]

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
