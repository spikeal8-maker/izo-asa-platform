import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView, type GuestView, type SessionList } from '../../shared/api'
import { Link } from '../../shell/router'
import './accounts.css'

const messages: Record<string, string> = {
  invalid_credentials: 'Не удалось войти. Проверьте адрес и пароль.',
  registration_rejected: 'Не удалось создать аккаунт. Возможно, такой адрес уже используется.',
  registration_disabled: 'Регистрация сейчас недоступна.',
  invalid_input: 'Проверьте поля. Пароль должен содержать от 8 до 128 символов.',
  rate_limited: 'Слишком много попыток. Попробуйте немного позже.',
  auth_busy: 'Сервер занят проверкой входа. Повторите попытку.',
  auth_not_configured: 'Авторизация временно недоступна.',
  csrf_rejected: 'Сессия устарела. Обновите страницу и повторите действие.',
  origin_rejected: 'Этот адрес приложения не разрешён сервером.',
  session_limit: 'Достигнут лимит активных сессий. Завершите ненужную сессию на другом устройстве.',
  guest_job_active: 'Дождитесь завершения пробной работы и затем создайте аккаунт.',
  guest_required: 'Пробная сессия завершилась. Можно зарегистрироваться как новый пользователь.',
}
function explanation(error: unknown) {
  return error instanceof ApiError ? messages[error.code] ?? 'Запрос отклонён сервером.'
    : 'Сервер недоступен. Повторите попытку после восстановления связи.'
}

export function AccountPage({ mode }: { mode: 'account' | 'login' | 'register' }) {
  const [auth, setAuth] = useState<AuthView | null>(null)
  const [guest, setGuest] = useState<GuestView | null>(null)
  const [sessions, setSessions] = useState<SessionList['sessions']>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const registering = mode === 'register'

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal }).then(async value => {
      setAuth(value)
      const result = await apiRequest<SessionList>('/api/v1/auth/sessions', { signal: controller.signal })
      setSessions(result.sessions)
    }).catch(reason => {
      if (controller.signal.aborted) return
      if (reason instanceof ApiError && reason.status === 401) { setAuth(null); setSessions([]) }
      else setError(explanation(reason))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [mode, reload])

  useEffect(() => {
    if (!registering) { setGuest(null); return }
    const controller = new AbortController()
    apiRequest<GuestView>('/api/v1/guest/me', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setGuest(value)
    }).catch(reason => {
      if (!controller.signal.aborted && !(reason instanceof ApiError && reason.status === 401))
        setError(explanation(reason))
    })
    return () => controller.abort()
  }, [registering])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = event.currentTarget
    const values = new FormData(form)
    const payload: Record<string, string> = {
      email: String(values.get('email') ?? ''), password: String(values.get('password') ?? ''),
    }
    if (registering) payload.display_name = String(values.get('display_name') ?? '')
    setBusy(true); setError('')
    try {
      const endpoint = registering && guest ? '/api/v1/guest/claim'
        : `/api/v1/auth/${registering ? 'register' : 'login'}`
      await apiRequest<AuthView>(endpoint, { method: 'POST', data: payload,
        csrf: registering && guest ? guest.csrf_token : undefined })
      window.location.assign('/')
    } catch (reason) {
      if (registering && reason instanceof ApiError && reason.code === 'guest_required') setGuest(null)
      setError(explanation(reason))
    } finally {
      const password = form.elements.namedItem('password') as HTMLInputElement | null
      if (password) password.value = ''
      payload.password = ''; setBusy(false)
    }
  }

  async function revoke(path: string, endsCurrent = false) {
    if (!auth || busy) return
    if (!window.confirm(endsCurrent ? 'Выйти из текущей сессии?' : 'Завершить выбранные сессии?')) return
    setBusy(true); setError('')
    try {
      await apiRequest<void>(path, { method: path.includes('/sessions/') && !path.endsWith('revoke-others') ? 'DELETE' : 'POST', csrf: auth.csrf_token })
      if (endsCurrent) { setAuth(null); setSessions([]); window.location.assign('/') }
      else setReload(value => value + 1)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) { setAuth(null); setSessions([]) }
      setError(explanation(reason))
    } finally { setBusy(false) }
  }

  if (!auth && !loading && mode !== 'account') return <section className="auth-page">
    <div className="auth-card">
      <p className="eyebrow">ИЗО АСА</p>
      <h1>{registering ? 'Создать аккаунт' : 'Войти'}</h1>
      <p>{registering
        ? guest ? 'Пробная работа останется в этом аккаунте. Укажите данные для продолжения.'
          : 'Сохраняйте работы, историю и баланс между устройствами.'
        : 'Продолжите работу с вашими проектами и галереей.'}</p>
      {error && <div className="field-error" role="alert">{error}</div>}
      <form onSubmit={submit} className="account-form">
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

  return <section className="account-page">
    <header className="page-heading"><p className="eyebrow">АККАУНТ</p><h1>Ваш профиль</h1><p>Управляйте способом входа, безопасностью и активными сессиями.</p></header>
    {error && <div className="field-error" role="alert">{error}<button disabled={busy} onClick={() => setReload(value => value + 1)}>Повторить</button></div>}
    {loading ? <p role="status">Загружаем аккаунт…</p> : auth ? <div data-testid="server-account" className="account-panel">
      <h2>{auth.account.display_name}</h2><p>{auth.account.email ?? 'Адрес не привязан'}</p>
      <div className="account-links"><Link href="/verify-email">Подтвердить почту</Link><Link href="/account/security">Изменить пароль</Link><Link href="/account/connections">Способы входа</Link></div>
      <h3>Активные сессии</h3>
      <ul className="session-list">{sessions.map(session => <li key={session.id}><div><strong>{session.current ? 'Это устройство' : 'Другое устройство'}</strong><small>{session.client_label}</small><small>{new Date(session.created_at * 1000).toLocaleString('ru-RU')}</small></div><button disabled={busy} onClick={() => void revoke(`/api/v1/auth/sessions/${session.id}`, session.current)}>Завершить</button></li>)}</ul>
      <div className="account-actions"><button disabled={busy || sessions.length < 2} onClick={() => void revoke('/api/v1/auth/sessions/revoke-others')}>Завершить другие</button><button disabled={busy} onClick={() => void revoke('/api/v1/auth/logout', true)}>Выйти</button></div>
    </div> : <div className="account-panel"><h2>Вы не вошли</h2><p>Войдите или создайте аккаунт, чтобы сохранять работы и историю.</p><div className="feed-actions"><Link className="primary" href="/login">Войти</Link><Link className="secondary" href="/register">Регистрация</Link></div></div>}
  </section>
}
