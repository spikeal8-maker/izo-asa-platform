import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView, type GuestView, type SessionList } from '../../shared/api'
import { AccountSessions, AuthEntry } from './AuthEntry'
import './accounts.css'

const formMessages: Record<string, string> = {
  invalid_credentials: 'Неверная почта или пароль.',
  registration_rejected: 'Не удалось создать аккаунт. Возможно, эта почта уже используется.',
  registration_disabled: 'Регистрация сейчас недоступна.',
  invalid_input: 'Проверьте введённые данные.',
  rate_limited: 'Слишком много попыток. Повторите позже.',
  guest_job_active: 'Дождитесь завершения пробной работы и затем создайте аккаунт.',
  guest_required: 'Пробная сессия завершилась. Можно зарегистрироваться как новый пользователь.',
}
function formExplanation(error: unknown, registering: boolean) {
  if (error instanceof ApiError && formMessages[error.code]) return formMessages[error.code]
  return registering ? 'Не удалось создать аккаунт. Повторите попытку.'
    : 'Не удалось выполнить вход. Повторите попытку.'
}
function accountExplanation(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === 'csrf_rejected') return 'Сессия устарела. Обновите страницу и повторите действие.'
    if (error.code === 'session_limit') return 'Достигнут лимит активных сессий. Завершите ненужную сессию на другом устройстве.'
  }
  return 'Не удалось выполнить действие. Повторите попытку.'
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
      else if (mode === 'account') setError(accountExplanation(reason))
      else { setAuth(null); setSessions([]) }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [mode, reload])

  useEffect(() => {
    if (!registering) { setGuest(null); return }
    const controller = new AbortController()
    setGuest(null)
    apiRequest<GuestView>('/api/v1/guest/me', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setGuest(value)
    }).catch(() => {
      if (!controller.signal.aborted) setGuest(null)
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
      const endpoint = registering && guest ? '/api/v1/guest/claim' : `/api/v1/auth/${registering ? 'register' : 'login'}`
      await apiRequest<AuthView>(endpoint, { method: 'POST', data: payload, csrf: registering && guest ? guest.csrf_token : undefined })
      window.location.assign('/')
    } catch (reason) {
      if (registering && reason instanceof ApiError && reason.code === 'guest_required') setGuest(null)
      setError(formExplanation(reason, registering))
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
      setError(accountExplanation(reason))
    } finally { setBusy(false) }
  }

  if (!auth && !loading && mode !== 'account') return <AuthEntry registering={registering} guest={guest} busy={busy} error={error} onSubmit={submit} />
  if (loading) return <section className="account-page"><p role="status">Загружаем аккаунт…</p></section>
  return <AccountSessions auth={auth} sessions={sessions} busy={busy} error={error}
    onReload={() => setReload(value => value + 1)} onRevoke={(path, current) => void revoke(path, current)} />
}
