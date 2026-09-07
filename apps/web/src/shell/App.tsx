import { useEffect, useRef, useState } from 'react'
import { detectHost } from '../platform/host'
import { ApiStatus } from './ApiStatus'
import { navigation } from './navigation'
import { Overview } from './Overview'
import { SectionPage } from './SectionPage'

function initialTheme(): 'light' | 'dark' {
  try { return localStorage.getItem('izo-theme') === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}

export function App() {
  const [theme, setTheme] = useState(initialTheme)
  const dialog = useRef<HTMLDialogElement>(null)
  const path = window.location.pathname.replace(/\/$/, '') || '/'
  const host = detectHost(window)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('izo-theme', theme) } catch { /* Storage may be disabled by host. */ }
  }, [theme])
  return <div className="app" data-platform={host}>
    <a className="skip-link" href="#main">К содержимому</a>
    <header className="topbar">
      <a href="/" className="brand" aria-label="ИЗО АСА — главная"><span className="brand-mark" aria-hidden="true">И</span>ИЗО АСА</a>
      <span className="build-label">Новая платформа</span>
      <div className="header-actions">
        <button onClick={() => setTheme(t => t === 'light' ? 'dark' : 'light')} aria-label="Переключить тему">{theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}</button>
        <button onClick={() => dialog.current?.showModal()}>О состоянии</button>
      </div>
    </header>
    <div className="layout">
      <aside className="sidebar"><nav aria-label="Разделы платформы">
        {navigation.map(item => <a href={item.path} key={item.path} aria-current={path === item.path ? 'page' : undefined}>{item.title}</a>)}
      </nav><p className="sidebar-note">Один интерфейс.<br />Любой экран.</p></aside>
      <div className="content">
        <div className="notice" role="note">Техническая версия · Генерация и регистрация ещё не подключены.</div>
        <main id="main" tabIndex={-1}>{path === '/' ? <Overview /> : <SectionPage path={path} />}</main>
        <footer><span>ИЗО АСА · Foundation 0</span><ApiStatus /></footer>
      </div>
    </div>
    <dialog ref={dialog} aria-labelledby="status-title">
      <h2 id="status-title">Что работает сейчас</h2>
      <p>Навигация, адаптивная оболочка, темы и соединение с API. Проверки инфраструктуры выполняются отдельно.</p>
      <p>Генерации, аккаунтов, платежей и реального входа через Telegram/MAX здесь пока нет.</p>
      <form method="dialog"><button className="primary">Понятно</button></form>
    </dialog>
  </div>
}
