import { useEffect, useState } from 'react'
import { detectHost } from '../platform/host'
import { ApiStatus } from './ApiStatus'
import { SectionPage } from './SectionPage'
import { Link, usePath } from './router'
import { Icon, type IconName } from '../shared/ui/Icon'
import { Dialog } from '../shared/ui/Dialog'
import { DemoProvider, useDemo } from '../features/prototype/DemoState'
import { Studio } from '../features/studio/Studio'
import { ResultPanel } from '../features/studio/ResultPanel'
import { Gallery } from '../features/gallery/Gallery'
import { AssetPage } from '../features/gallery/AssetPage'
import { AccountPage } from '../features/accounts/AccountPage'
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

function AppContent() {
  const [theme, setTheme] = useState(initialTheme)
  const [about, setAbout] = useState(false)
  const [resetting, setResetting] = useState(false)
  const path = usePath()
  const { state, reset, setEmptyBalance, storageAvailable } = useDemo()
  const host = detectHost(window)
  const studio = ['/', '/app', '/image', '/studio/image'].includes(path)
  const gallery = path === '/gallery'
  const account = ['/account', '/account/sessions', '/login', '/register'].includes(path)
  const detail = path.startsWith('/gallery/')
  const jobs = path === '/jobs' || path.startsWith('/jobs/')
  const activeJob = state.job?.state === 'running'
  const balance = state.balance - (activeJob ? state.job!.cost : 0)
  const knownJob = path === '/jobs' || path === `/jobs/${state.job?.id}`

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('izo-theme', theme) } catch { /* Hosts may disable storage. */ }
  }, [theme])
  useEffect(() => {
    const heading = document.querySelector<HTMLElement>('main h1')
    if (heading) {
      heading.tabIndex = -1
      heading.focus({ preventScroll: true })
      document.title = `${heading.textContent} · ИЗО АСА`
    }
  }, [path])

  return <div className="app" data-platform={host}>
    <a className="skip-link" href="#main">К содержимому</a>
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="ИЗО АСА — главная">
        <span className="brand-mark"><Icon name="spark" /></span>
        <span>ИЗО АСА<small>CREATIVE STUDIO</small></span>
      </Link>
      <span className="sidebar-label">ПРОСТРАНСТВО</span>
      <nav aria-label="Разделы платформы">
        {navigation.map(item => {
          const selected = item.href === '/image' ? studio
            : item.href === '/gallery' ? gallery || detail : path.startsWith(item.href)
          return <Link href={item.href} key={item.href} aria-label={item.title}
            className={selected ? 'active' : ''} aria-current={selected ? 'page' : undefined}>
            <Icon name={item.icon} /><span>{item.title}</span>
            {item.href === '/gallery' && state.works.length > 0 && <small aria-hidden="true">{state.works.length}</small>}
          </Link>
        })}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-card">
          <Icon name="cube" /><strong>Одно место.<br />Много возможностей.</strong>
          <p>Изображения, видео, звук, 3D и чат — в общей системе.</p>
          <span>ПРОТОТИП / 01</span>
        </div>
        <Link href="/admin" className="staff-link"><Icon name="sliders" /> Пример админки</Link>
      </div>
    </aside>
    <div className="app-body">
      <header className="topbar">
        <Link className="mobile-brand" href="/"><Icon name="spark" /> ИЗО АСА</Link>
        <div className="breadcrumb">Рабочее пространство <span>/</span>
          <strong>{account ? 'Аккаунт' : studio ? 'Студия' : gallery || detail ? 'Мои работы' : jobs ? 'Задания' : 'Обзор'}</strong>
        </div>
        <div className="header-actions">
          <button className="balance-button" onClick={() => setAbout(true)} aria-label={`Демо-баланс: ${balance} баллов`}>
            <Icon name="spark" />{balance}<span>демо-баллов</span>
          </button>
          <button className="icon-button" aria-label="Переключить тему"
            onClick={() => setTheme(value => value === 'light' ? 'dark' : 'light')}><Icon name="sun" /></button>
          <Link className="avatar" href="/account" aria-label="Аккаунт"><Icon name="user" /></Link>
        </div>
      </header>
      <div className="content">
        <div className="demo-notice" role="note">
          <span><i />{account ? 'Серверный аккаунт' : 'Интерактивный прототип'} <span className="notice-detail">· без реальных генераций и платежей</span></span>
          <button onClick={() => setAbout(true)}>О состоянии <Icon name="info" /></button>
        </div>
        {!storageAvailable && !account && <p className="field-error" role="alert">
          Хранение в этой вкладке недоступно. После обновления демо-данные не сохранятся.
        </p>}
        <main id="main" tabIndex={-1}>
          {account ? <AccountPage key={path} mode={path === '/register' ? 'register' : path === '/login' ? 'login' : 'account'} />
            : studio ? <Studio />
            : gallery ? <Gallery />
            : detail ? <AssetPage id={path.slice('/gallery/'.length)} />
            : jobs ? <>
              <header className="page-heading">
                <p className="eyebrow">ПРОЦЕСС</p><h1>Задания</h1>
                <p>Здесь показана только последняя тестовая задача этой вкладки.</p>
              </header>
              {state.job && knownJob ? <div className="job-detail"><ResultPanel /></div>
                : <div className="gallery-empty"><h2>Задание не найдено</h2>
                  <Link className="primary" href="/image">Открыть студию</Link>
                </div>}
            </> : <>
              <SectionPage path={path} />
              {path === '/admin' && <section className="admin-sample">
                <h2>Карточка пользователя · образец</h2>
                <p>Вымышленные сведения для оценки таблицы. Административных API и прав пока нет.</p>
                <dl className="summary-list">
                  <div><dt>Пользователь</dt><dd>Демо-пользователь 01</dd></div>
                  <div><dt>Статус</dt><dd>Тестовый</dd></div>
                  <div><dt>Баланс макета</dt><dd>{balance} демо-баллов</dd></div>
                </dl>
              </section>}
            </>}
        </main>
        <footer><span>ИЗО АСА · AUTH-001 / UX-001</span><ApiStatus /></footer>
      </div>
    </div>
    <Dialog open={about} title="Что работает сейчас" onClose={() => setAbout(false)}>
      <p>Студия, локальный предпросмотр исходника, тестовая задача, её отмена/ошибка, просмотр и скачивание SVG-примера. Это макет, не AI-сервис.</p>
      <p>Аккаунт и сессии работают через сервер. Генерация, баланс студии и её работы остаются демо этой вкладки. Почта и вход через Telegram/MAX ещё не подключены.</p>
      <label className="demo-checkbox">
        <input type="checkbox" checked={state.balance === 0} disabled={activeJob}
          onChange={event => setEmptyBalance(event.target.checked)} /> Нулевой демо-баланс
      </label>
      <div className="dialog-actions">
        <button className="secondary" onClick={() => { setAbout(false); setResetting(true) }}>Сбросить демо</button>
        <button className="primary" onClick={() => setAbout(false)}>Понятно</button>
      </div>
    </Dialog>
    <Dialog open={resetting} title="Сбросить данные прототипа?" onClose={() => setResetting(false)}>
      <p>Демо-описание, работы и текущая тестовая задача будут удалены из этой вкладки. Серверный аккаунт не удаляется.</p>
      <button className="danger-button" onClick={() => { reset(); setResetting(false) }}>Подтвердить сброс</button>
    </Dialog>
  </div>
}
export function App() { return <DemoProvider><AppContent /></DemoProvider> }
