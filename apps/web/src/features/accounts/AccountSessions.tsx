import type { AuthView, SessionList } from '../../shared/api'
import { Link } from '../../shell/router'

export function AccountSessions({ auth, sessions, busy, error, onReload, onRevoke }: {
  auth: AuthView | null
  sessions: SessionList['sessions']
  busy: boolean
  error: string
  onReload: () => void
  onRevoke: (path: string, endsCurrent?: boolean) => void
}) {
  return <section className="account-page">
    <header className="page-heading"><p className="eyebrow">АККАУНТ</p><h1>Ваш профиль</h1><p>Управляйте способом входа, безопасностью и активными сессиями.</p></header>
    {error && <div className="field-error" role="alert">{error}<button disabled={busy} onClick={onReload}>Повторить</button></div>}
    {auth ? <div data-testid="server-account" className="account-panel">
      <div className="account-summary"><div><small>Профиль</small><h2>{auth.account.display_name}</h2><p>{auth.account.email ?? 'Адрес не привязан'}</p></div>
        <Link className="secondary" href="/account/credits">Баланс</Link></div>
      <nav className="account-links" aria-label="Настройки аккаунта"><Link href="/verify-email">Подтвердить почту</Link><Link href="/account/security">Изменить пароль</Link><Link href="/account/connections">Способы входа</Link></nav>
      <div className="account-section-heading"><div><small>Безопасность</small><h3>Активные сессии</h3></div><span>{sessions.length}</span></div>
      <ul className="session-list">{sessions.map(session => <li key={session.id}><div><strong>{session.current ? 'Это устройство' : 'Другое устройство'}</strong><small>{session.client_label}</small><small>{new Date(session.created_at * 1000).toLocaleString('ru-RU')}</small></div><button disabled={busy} onClick={() => onRevoke(`/api/v1/auth/sessions/${session.id}`, session.current)}>Завершить</button></li>)}</ul>
      <div className="account-actions"><button disabled={busy || sessions.length < 2} onClick={() => onRevoke('/api/v1/auth/sessions/revoke-others')}>Завершить другие</button><button disabled={busy} onClick={() => onRevoke('/api/v1/auth/logout', true)}>Выйти</button></div>
    </div> : <div className="account-panel account-empty"><h2>Вы не вошли</h2><p>Войдите или создайте аккаунт, чтобы сохранять работы и историю.</p><div className="feed-actions"><Link className="primary" href="/login">Войти</Link><Link className="secondary" href="/register">Регистрация</Link></div></div>}
  </section>
}
