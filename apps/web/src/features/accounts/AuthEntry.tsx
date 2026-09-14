import type { FormEventHandler } from 'react'
import type { GuestView } from '../../shared/api'
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
