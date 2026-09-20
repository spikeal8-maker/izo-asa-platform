import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import type { AuthView } from '../shared/api'
import { apiRequest } from '../shared/api'
import type { Credits } from '../shared/workspace-api'
import { Icon, type IconName } from '../shared/ui/Icon'
import { Link } from './router'
import { workspaces } from './navigation'
import './product-nav.css'

const icons: Record<(typeof workspaces)[number]['id'], IconName> = {
  chat: 'chat', image: 'image', video: 'video', audio: 'audio', '3d': 'cube',
}
const socialLinks = [
  { label: 'VK', short: 'VK', href: null },
  { label: 'Instagram', short: 'IG', href: null },
  { label: 'Telegram', short: 'TG', href: 'https://t.me/izo_asa_bot' },
  { label: 'MAX', short: 'MAX', href: 'https://max.ru/id231408577954_4_bot' },
] as const

function menuKeyboard(event: KeyboardEvent<HTMLDivElement>, close?: () => void) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close?.()
    return
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
    '[role="menuitem"]:not([aria-disabled="true"]), [role="menuitemradio"]:not([aria-disabled="true"])',
  )).filter(item => item.offsetParent !== null)
  if (!items.length) return
  event.preventDefault()
  const current = items.indexOf(document.activeElement as HTMLElement)
  let next = current
  if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = items.length - 1
  else if (event.key === 'ArrowDown') next = current < 0 ? 0 : (current + 1) % items.length
  else next = current < 0 ? items.length - 1 : (current - 1 + items.length) % items.length
  items[next]?.focus()
}

export function AccountMenu({ className, theme, onThemeChange, onLogout, onClose, onEscape }: {
  className: string
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
  onClose?: () => void
  onEscape?: () => void
}) {
  const closeFromKeyboard = () => {
    if (onEscape) onEscape()
    else onClose?.()
  }
  useEffect(() => {
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      closeFromKeyboard()
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [onEscape, onClose])

  return <div className={className} role="menu" onKeyDown={event => menuKeyboard(event, closeFromKeyboard)}>
    <Link href="/account" role="menuitem" onClick={onClose}>Аккаунт</Link>
    <Link href="/account/credits" role="menuitem" onClick={onClose}>Токены</Link>
    <Link href="/account/security" role="menuitem" onClick={onClose}>Настройки</Link>
    <Link href="/help" role="menuitem" onClick={onClose}>Помощь</Link>

    <div className="theme-row" role="group" aria-label="Переключить тему">
      <span>Тема</span>
      <button role="menuitemradio" aria-checked={theme === 'light'} onClick={() => onThemeChange('light')}>Светлая</button>
      <button role="menuitemradio" aria-checked={theme === 'dark'} onClick={() => onThemeChange('dark')}>Тёмная</button>
    </div>

    <div className="social-links" aria-label="Социальные сети">
      {socialLinks.map(item => item.href
        ? <a key={item.label} className="social-link" href={item.href} target="_blank" rel="noreferrer"
            role="menuitem" aria-label={item.label} title={item.label}>{item.short}</a>
        : <span key={item.label} className="social-link disabled" role="menuitem" aria-disabled="true"
            aria-label={item.label} title={`${item.label}: ссылка не настроена`}>{item.short}</span>)}
    </div>

    <button className="menu-logout" role="menuitem" onClick={() => { onClose?.(); onLogout() }}>Выйти</button>
  </div>
}

export function TopBar({ path, auth, theme, onThemeChange, onLogout }: {
  path: string
  auth: AuthView | null | undefined
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
}) {
  const [credits, setCredits] = useState<number | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const profile = useRef<HTMLDivElement>(null)
  const profileButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    setCredits(null)
    if (!auth || path === '/gallery' || path.startsWith('/gallery/')) return
    const controller = new AbortController()
    apiRequest<Credits>('/api/v1/credits', { signal: controller.signal })
      .then(value => setCredits(value.balance.available))
      .catch(() => setCredits(null))
    return () => controller.abort()
  }, [auth?.account.id, path])

  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!profile.current?.contains(event.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setMenuOpen(false)
      requestAnimationFrame(() => profileButton.current?.focus())
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [menuOpen])

  const initial = auth?.account.display_name.trim().slice(0, 1).toUpperCase() || 'А'
  const tokenHref = auth ? '/account/credits' : '/login'
  const mainTokens = auth && credits !== null ? String(credits) : '0'

  return <header className="global-header" data-testid="global-header">
    <div className="header-left">
      <Link className="global-brand" href="/" aria-label="ИЗО АСА">
        <img className="brand-favicon" src="/favicon.svg" alt="" aria-hidden="true" />
        <span className="brand-name"><span className="brand-izo">ИЗО</span><span className="brand-asa">АСА</span></span>
      </Link>
      <nav className="explore-nav" aria-label="Лента и Галерея">
        <Link className={path === '/feed' ? 'header-route active' : 'header-route'} href="/feed" aria-label="Лента">
          <Icon name="feed" /><span>Лента</span>
        </Link>
        <Link className={path === '/gallery' ? 'header-route active' : 'header-route'} href="/gallery" aria-label="Галерея">
          <Icon name="grid" /><span>Галерея</span>
        </Link>
      </nav>
    </div>

    <nav className="product-nav" aria-label="Творческие инструменты ИЗО АСА">
      {workspaces.map(item => <Link key={item.id} href={item.path}
        className={path === item.path ? 'product-tab active' : 'product-tab'}
        aria-current={path === item.path ? 'page' : undefined} aria-label={item.title}>
        <Icon name={icons[item.id]} />
        <span className="desktop-label">{item.title}</span><span className="mobile-label">{item.mobileTitle}</span>
      </Link>)}
    </nav>

    <div className="header-right">
      <div className="token-box" data-testid="global-token-group" aria-label="Баланс токенов">
        <Link className="token-pill daily" data-testid="token-daily" href={tokenHref}
          aria-label="Дневные токены: 0 из 0" title="Дневные токены: 0 из 0">
          <Icon name="sun" /><span className="token-value">0/0</span>
        </Link>
        <Link className="token-pill main" data-testid="token-main" href={tokenHref}
          aria-label={`Основные токены: ${mainTokens}`} title={`Основные токены: ${mainTokens}`}>
          <Icon name="gem" /><span className="token-value">{mainTokens}</span>
        </Link>
      </div>
      {auth && <button type="button" className="header-theme-toggle" aria-label="Переключить тему"
        data-theme-value={theme} onClick={() => onThemeChange(theme === 'light' ? 'dark' : 'light')}>
        <Icon name="sun" />
      </button>}

      {auth ? <div className="profile-control" ref={profile}
        onKeyDown={event => {
          if (event.key !== 'Escape' || !menuOpen) return
          event.preventDefault()
          setMenuOpen(false)
          requestAnimationFrame(() => profileButton.current?.focus())
        }}>
        <button ref={profileButton} className="header-avatar" aria-label="Профиль" aria-expanded={menuOpen}
          onClick={() => setMenuOpen(value => !value)}>{initial}</button>
        {menuOpen && <AccountMenu className="profile-menu" theme={theme} onThemeChange={onThemeChange}
          onLogout={onLogout} onClose={() => setMenuOpen(false)}
          onEscape={() => { setMenuOpen(false); requestAnimationFrame(() => profileButton.current?.focus()) }} />}
      </div> : auth === null ? <Link className="login-button" href="/login">Войти</Link> : null}
    </div>
  </header>
}
