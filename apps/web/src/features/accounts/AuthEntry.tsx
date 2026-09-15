import type { FormEventHandler } from 'react'
import type { AuthView, GuestView, SessionList } from '../../shared/api'
import { Link } from '../../shell/router'

export function AuthEntry({ registering, guest, busy, error, onSubmit }: {
  registering: boolean
  guest: GuestView | null
  busy: boolean
  error: string
  onSubmit: FormEventHandler<HTMLFormElement>
}) {
  return <section className="auth-page">
    <div className="auth-card">
      <p className="eyebrow">ИЗО АСА</p>
      <h1>{registering ? 'Создать аккаунт' : 'Войти'}</h1>
      <p>{registering
        ? guest ? 'Пробная работа останется в этом аккаунте. Укажите данные для продолжения.'
          : 'Сохраняйте работы, историю и баланс между устройствами.'
        : 'Продолжите работу с вашими проектами и галереей.'}</p>
      {error && <div className="field-error" role="alert">{error}</div>}
      <form onSubmit={onSubmit} className="account-form">
        {registering && <label>Имя<input name="display_name" autoComplete="nickname" required maxLength={80} /></label>}
        <label>Электронная почта<input name="email" type="email" autoComplete="username" required maxLength={254} /></label>
        <label>Пароль<input name="password" type="password" aria-label="Пароль"
          aria-describedby={registering ? 'password-help' : undefined}
          autoComplete={registering ? 'new-password' : 'current-password'} required minLength={registering ? 8 : 1} maxLength={128} />
          {registering && <small id="password-help">Минимум 8 символов. Можно использовать длинную фразу.</small>}</label>
        <button className="primary full-width" type="submit" disabled={busy}>{busy ? 'Проверяем…' : registering ? 'Создать аккаунт' : 'Войти'}</button>
      </form>
      {!registering && <p className="auth-minor"><Link href="/password/forgot">Забыли пароль?</Link></p>}
      <p className="auth-switch"><Link href={registering ? '/login' : '/register'}>{registering ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}</Link></p>
    </div>
  </section>
}

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
