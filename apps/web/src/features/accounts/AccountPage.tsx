import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView, type SessionList } from '../../shared/api'
import { Link } from '../../shell/router'
import './accounts.css'

const messages: Record<string, string> = {
  invalid_credentials: 'Не удалось войти. Проверьте адрес и пароль.',
  registration_rejected: 'Регистрация не выполнена. Проверьте приглашение или попробуйте вход в существующий аккаунт.',
  registration_disabled: 'Регистрация на этом стенде отключена.',
  invalid_input: 'Проверьте поля. Новый пароль должен содержать от 15 до 128 символов.',
  rate_limited: 'Слишком много попыток. Сделайте паузу перед повтором.',
  auth_busy: 'Сервер занят проверкой входа. Повторите попытку.',
  auth_not_configured: 'Авторизация на этом стенде ещё не настроена.',
  csrf_rejected: 'Защита сессии не прошла проверку. Обновите страницу.',
  origin_rejected: 'Адрес этого сайта не разрешён в конфигурации сервера.',
  session_limit: 'Достигнут лимит сессий. Завершите ненужную сессию на другом устройстве.',
}
function explanation(error: unknown) {
  return error instanceof ApiError ? messages[error.code] ?? 'Запрос отклонён сервером.'
    : 'Сервер недоступен. Данные не сохранены; повторите после восстановления связи.'
}

export function AccountPage({ mode }: { mode: 'account' | 'login' | 'register' }) {
  const [auth, setAuth] = useState<AuthView | null>(null)
  const [sessions, setSessions] = useState<SessionList['sessions']>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const registering = mode === 'register'

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = event.currentTarget
    const values = new FormData(form)
    const payload: Record<string, string> = {
      email: String(values.get('email') ?? ''), password: String(values.get('password') ?? ''),
    }
    if (registering) {
      payload.display_name = String(values.get('display_name') ?? '')
      payload.invite_code = String(values.get('invite_code') ?? '').trim()
    }
    setBusy(true)
    setError('')
    try {
      await apiRequest<AuthView>(`/api/v1/auth/${registering ? 'register' : 'login'}`, { method: 'POST', data: payload })
      // Full navigation proves that the server cookie, not component state, owns identity.
      window.location.assign('/account')
    } catch (reason) { setError(explanation(reason)) }
    finally {
      const password = form.elements.namedItem('password') as HTMLInputElement | null
      if (password) password.value = ''
      payload.password = ''
      setBusy(false)
    }
  }

  async function revoke(path: string, endsCurrent = false) {
    if (!auth || busy) return
    if (!window.confirm(endsCurrent ? 'Завершить текущую серверную сессию?' : 'Завершить выбранные сессии?')) return
    setBusy(true)
    setError('')
    try {
      await apiRequest<void>(path, { method: path.includes('/sessions/') && !path.endsWith('revoke-others')
        ? 'DELETE' : 'POST', csrf: auth.csrf_token })
      if (endsCurrent) { setAuth(null); setSessions([]) }
      else setReload(value => value + 1)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) { setAuth(null); setSessions([]) }
      setError(explanation(reason))
    } finally { setBusy(false) }
  }

  return <section className="account-page">
    <header className="page-heading"><p className="eyebrow">СЕРВЕРНЫЙ АККАУНТ · AUTH-001</p>
      <h1>{auth || mode === 'account' ? 'Аккаунт' : registering ? 'Регистрация' : 'Вход'}</h1>
      <p>Аккаунт и сессии сохраняются в PostgreSQL. Студия и её демо-баланс пока остаются отдельным прототипом.</p>
    </header>
    {error && <div className="field-error" role="alert">{error}
      <button disabled={busy} onClick={() => setReload(value => value + 1)}>Повторить проверку сессии</button>
    </div>}
    {loading ? <p role="status">Проверяем серверную сессию…</p> : auth ? <div data-testid="server-account" className="account-panel">
      <h2>{auth.account.display_name}</h2>
      <p>{auth.account.email ?? 'Адрес не привязан'} · код {auth.account.public_code}</p>
      <p>Адрес {auth.account.email_verified ? 'подтверждён' : 'ещё не подтверждён'}. Подтверждение и восстановление работают через тестовые письма; реальная отправка отключена.</p>
      <p>Полномочия: {auth.account.permissions.length ? auth.account.permissions.join(', ') : 'обычный пользователь, без административных прав'}.</p>
      <p><Link href="/verify-email">Подтвердить почту</Link> · <Link href="/account/security">Изменить пароль</Link> · <Link href="/account/connections">Способы входа</Link></p>
      <h3>Активные сессии</h3>
      <ul className="session-list">{sessions.map(session => <li key={session.id}>
        <div><strong>{session.current ? 'Эта сессия' : 'Другое устройство'}</strong>
          <small>{session.client_label}</small><small>Создана: {new Date(session.created_at * 1000).toLocaleString('ru-RU')}</small></div>
        <button disabled={busy} onClick={() => void revoke(`/api/v1/auth/sessions/${session.id}`, session.current)}>Завершить</button>
      </li>)}</ul>
      <div className="account-actions">
        <button disabled={busy || sessions.length < 2} onClick={() => void revoke('/api/v1/auth/sessions/revoke-others')}>Завершить другие сессии</button>
        <button disabled={busy} onClick={() => void revoke('/api/v1/auth/logout', true)}>Выйти</button>
      </div>
    </div> : <div className="account-panel">
      <p>Вход через Telegram/MAX ещё не подключён. Данные Mini App не предоставляют права без серверной проверки.</p>
      <form onSubmit={submit} className="account-form">
        {registering && <label>Имя<input name="display_name" autoComplete="nickname" required maxLength={80} /></label>}
        <label>Электронная почта<input name="email" type="email" autoComplete="username" required maxLength={254} /></label>
        <label>Пароль<input name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'}
          required minLength={registering ? 15 : 1} maxLength={128} /></label>
        {registering && <label>Одноразовое приглашение<input name="invite_code" autoComplete="off" required minLength={43} maxLength={43} />
          <small>Приглашение выдаёт оператор закрытого тестового стенда. Оно не даёт административных прав.</small></label>}
        <button className="primary" type="submit" disabled={busy}>{busy ? 'Проверяем…' : registering ? 'Создать аккаунт' : 'Войти'}</button>
      </form>
      <p><Link href="/password/forgot">Забыли пароль?</Link></p>
      <p><Link href={registering ? '/login' : '/register'}>{registering ? 'Уже есть аккаунт — войти' : 'Зарегистрироваться по приглашению'}</Link></p>
    </div>}
  </section>
}
