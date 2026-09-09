import { useEffect, useState } from 'react'
import { detectHost } from '../platform/host'
import { ApiStatus } from './ApiStatus'
import { SectionPage } from './SectionPage'
import { Link, usePath } from './router'
import { Icon, type IconName } from '../shared/ui/Icon'
import { Dialog } from '../shared/ui/Dialog'
import { Studio } from '../features/studio/Studio'
import { ResultPanel } from '../features/studio/ResultPanel'
import { Gallery } from '../features/gallery/Gallery'
import { AssetPage } from '../features/gallery/AssetPage'
import { AccountPage } from '../features/accounts/AccountPage'
import { SecurityPage, securityPages } from '../features/accounts/SecurityPage'
import { AdminPage, AdminLink } from '../features/admin/AdminPage'
import { CreditsPage } from '../features/credits/CreditsPage'
import './layout.css'

function initialTheme(): 'light' | 'dark' {
  try { return localStorage.getItem('izo-theme') === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}
const navigation: { href: string; title: string; icon: IconName }[] = [
  { href: '/image', title: 'Студия', icon: 'spark' },
  { href: '/gallery', title: 'Галерея', icon: 'grid' },
  { href: '/feed', title: 'Лента', icon: 'feed' },
  { href: '/jobs', title: 'Задания', icon: 'clock' },
]
export function App() {
  const [theme, setTheme] = useState(initialTheme)
  const [about, setAbout] = useState(false)
  const path = usePath()
  const host = detectHost(window)
  const studio = ['/', '/app', '/image', '/studio/image'].includes(path)
  const gallery = path === '/gallery'
  const security = securityPages[path]
  const account = !!security || ['/account', '/account/sessions', '/login', '/register'].includes(path)
  const credits = path === '/account/credits'
  const admin = path === '/admin' || path.startsWith('/admin/')
  const detail = path.startsWith('/gallery/')
  const jobs = path === '/jobs' || path.startsWith('/jobs/')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('izo-theme', theme) } catch { /* Optional preference only. */ }
  }, [theme])
  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('main h1')
    if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); document.title = `${heading.textContent} · ИЗО АСА` }
  }, [path])
  return <div className="app" data-platform={host}>
    <a className="skip-link" href="#main">К содержимому</a>
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="ИЗО АСА — главная"><span className="brand-mark"><Icon name="spark" /></span>
        <span>ИЗО АСА<small>CREATIVE STUDIO</small></span></Link>
      <span className="sidebar-label">ПРОСТРАНСТВО</span>
      <nav aria-label="Разделы платформы">{navigation.map(item => {
        const selected = item.href === '/image' ? studio : item.href === '/gallery' ? gallery || detail : path.startsWith(item.href)
        return <Link href={item.href} key={item.href} aria-label={item.title} className={selected ? 'active' : ''}
          aria-current={selected ? 'page' : undefined}><Icon name={item.icon} /><span>{item.title}</span></Link>
      })}</nav>
      <div className="sidebar-bottom"><div className="sidebar-card"><Icon name="cube" /><strong>Одно место.<br />Много возможностей.</strong>
        <p>Серверные задания и личные файлы. Видео, звук, 3D и чат — следующие направления.</p><span>ТЕСТОВАЯ ПЛАТФОРМА</span></div>
        <Link href="/account/credits" className="staff-link"><Icon name="spark" /> Баланс и история</Link>
        {(account || credits || admin) && <AdminLink path={path} />}</div>
    </aside>
    <div className="app-body"><header className="topbar">
      <Link className="mobile-brand" href="/"><Icon name="spark" /> ИЗО АСА</Link>
      <div className="breadcrumb">Рабочее пространство <span>/</span>
        <strong>{admin ? 'Администрирование' : account || credits ? 'Аккаунт' : studio ? 'Студия' : gallery || detail ? 'Мои работы' : jobs ? 'Задания' : 'Обзор'}</strong></div>
      <div className="header-actions"><Link className="balance-button" href="/account/credits"><Icon name="spark" /> Баллы</Link>
        <button className="icon-button" aria-label="Переключить тему" onClick={() => setTheme(v => v === 'light' ? 'dark' : 'light')}><Icon name="sun" /></button>
        <Link className="avatar" href="/account" aria-label="Аккаунт"><Icon name="user" /></Link></div>
    </header><div className="content"><div className="demo-notice" role="note">
      <span><i />Тестовая платформа <span className="notice-detail">· серверное хранение, без AI-инференса и платежей</span></span>
      <button onClick={() => setAbout(true)}>О состоянии <Icon name="info" /></button></div>
      <main id="main" tabIndex={-1}>
        {admin ? <AdminPage key={path} path={path} /> : credits ? <CreditsPage />
          : security ? <SecurityPage key={path} mode={security} />
          : account ? <AccountPage key={path} mode={path === '/register' ? 'register' : path === '/login' ? 'login' : 'account'} />
          : studio ? <Studio key={path} /> : gallery ? <Gallery key={path} />
          : detail ? <AssetPage key={path} id={path.slice('/gallery/'.length)} />
          : jobs ? <ResultPanel key={path} id={path === '/jobs' ? undefined : path.slice('/jobs/'.length)} />
          : <SectionPage path={path} />}
      </main><footer><span>ИЗО АСА · IMAGE-001</span><ApiStatus /></footer>
    </div></div>
    <Dialog open={about} title="Что работает сейчас" onClose={() => setAbout(false)}>
      <p>Аккаунт, баллы, планы, задания и приватные файлы используют общий сервер. В студии нет отдельного демо-баланса и вымышленных работ.</p>
      <p>Пока подключён только диагностический исполнитель: он создаёт PNG с отметкой TEST ONLY, а не изображение нейросети. Цена подтверждается перед запуском; расходуются баллы тестового стенда.</p>
      <p>AI-провайдеры, настоящая почта, Telegram/MAX, видео, звук, 3D, лента, удаление и публикация файлов ещё не подключены.</p>
      <button className="primary" onClick={() => setAbout(false)}>Понятно</button>
    </Dialog>
  </div>
}
