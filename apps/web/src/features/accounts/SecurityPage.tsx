import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import type { components } from '../../shared/api.generated'
import { Link } from '../../shell/router'
import './accounts.css'

type Receipt = components['schemas']['MailReceipt']
type Mode = 'verify' | 'forgot' | 'reset' | 'change' | 'connections'
export const securityPages: Record<string, Mode> = {
  '/verify-email': 'verify', '/password/forgot': 'forgot', '/password/reset': 'reset',
  '/account/security': 'change', '/account/connections': 'connections',
}
const titles: Record<Mode, string> = {
  verify: 'Подтверждение почты', forgot: 'Восстановление доступа', reset: 'Новый пароль',
  change: 'Безопасность аккаунта', connections: 'Способы входа',
}
const errors: Record<string, string> = {
  invalid_challenge: 'Ссылка недействительна, истекла или уже использована. Запросите новую.',
  reauth_required: 'Текущий пароль не подтверждён. Проверьте его или восстановите доступ.',
  auth_required: 'Войдите в свой аккаунт и снова откройте ссылку из письма.',
  invalid_input: 'Проверьте код и пароли. Новый пароль: 15–128 символов, оба поля должны совпадать.',
  recovery_not_configured: 'Проверка почты на этом стенде ещё не настроена.',
  csrf_rejected: 'Сессия изменилась. Обновите страницу.',
  rate_limited: 'Слишком много попыток. Повторите позже.',
  account_restricted: 'Действие ограничено для этого аккаунта. Обратитесь к оператору.',
}
function explanation(reason: unknown): string {
  return reason instanceof ApiError ? errors[reason.code] ?? 'Запрос отклонён сервером.'
    : 'Нет связи с сервером. Операция не подтверждена.'
}
function fragmentProof(): string {
  const value = new URLSearchParams(window.location.hash.slice(1)).get('token') ?? ''
  return /^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/.test(value) ? value : ''
}

export function SecurityPage({ mode }: { mode: Mode }) {
  const needsSession = ['verify', 'change', 'connections'].includes(mode)
  const [auth, setAuth] = useState<AuthView | null>(null)
  const [loading, setLoading] = useState(needsSession)
  const [proof, setProof] = useState(fragmentProof)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [finished, setFinished] = useState(false)

  useEffect(() => {
    // Read fragment before this effect; never consume a proof on GET/mount.
    // Tokens leave the address bar and are never persisted as browser identity.
    if (window.location.hash) window.history.replaceState(window.history.state, '', window.location.pathname)
    if (!needsSession) return
    const controller = new AbortController()
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setAuth(value) })
      .catch(reason => { if (!controller.signal.aborted) setError(explanation(reason)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [needsSession])

  async function requestVerification() {
    if (!auth || busy) return
    setBusy(true); setError('')
    try {
      await apiRequest<Receipt>('/api/v1/auth/email/verification/request', {
        method: 'POST', data: {}, csrf: auth.csrf_token,
      })
      setNotice('Запрос принят. На этом стенде письмо доступно только в тестовом ящике оператора.')
    } catch (reason) { setError(explanation(reason)) }
    finally { setBusy(false) }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = event.currentTarget
    const values = new FormData(form)
    const password = String(values.get('password') ?? '')
    const confirmation = String(values.get('confirmation') ?? '')
    if (['reset', 'change'].includes(mode) && password !== confirmation) {
      setError('Пароли не совпадают.'); return
    }
    const path = mode === 'verify' ? '/email/verification/confirm' : '/password/' + mode
    const data = mode === 'verify' ? { token: proof }
      : mode === 'forgot' ? { email: String(values.get('email') ?? '') }
      : mode === 'reset' ? { token: proof, password, confirmation }
      : { current_password: String(values.get('current_password') ?? ''), password, confirmation }
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest<void | Receipt>('/api/v1/auth' + path, {
        method: 'POST', data, csrf: auth?.csrf_token,
      })
      setNotice(mode === 'verify' ? 'Адрес подтверждён на сервере.'
        : mode === 'forgot' ? 'Если адрес подтверждён и восстановление разрешено, подготовлено тестовое письмо. Реальная отправка отключена.'
        : 'Пароль изменён. Все прежние сессии завершены. Войдите с новым паролем.')
      if (mode !== 'forgot') { setFinished(true); setProof('') }
    } catch (reason) { setError(explanation(reason)) }
    finally {
      for (const field of ['password', 'confirmation', 'current_password']) {
        const input = form.elements.namedItem(field) as HTMLInputElement | null
        if (input) input.value = ''
      }
      setBusy(false)
    }
  }

  return <section className="account-page">
    <header className="page-heading"><p className="eyebrow">ЗАЩИТА АККАУНТА · AUTH-002</p>
      <h1>{titles[mode]}</h1>
      <p>Проверки выполняются сервером. Доставка пока только тестовая: настоящие письма не отправляются.</p>
    </header>
    <div className="account-panel">
      {error && <p className="field-error" role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {loading ? <p role="status">Проверяем сессию…</p>
        : needsSession && !auth ? <p><Link href="/login">Войти в аккаунт</Link></p>
        : finished ? <p><Link href={mode === 'verify' ? '/account' : '/login'}>
          {mode === 'verify' ? 'Вернуться в аккаунт' : 'Войти с новым паролем'}</Link></p>
        : mode === 'connections' ? <>
          <h2>Электронная почта</h2><p>{auth?.account.email}</p>
          <p>{auth?.account.email_verified ? 'Подтверждена' : 'Не подтверждена'}</p>
          <p>Почта и пароль — текущий способ входа. Удаление последнего способа и привязка Telegram/MAX здесь не включены.</p>
          <Link href="/verify-email">Проверить адрес</Link>
        </> : <>
          {mode === 'verify' && <>
            <p>Подтверждается адрес вашего текущего аккаунта: {auth?.account.email}.</p>
            <button disabled={busy} onClick={() => void requestVerification()}>Запросить тестовое письмо</button>
          </>}
          <form className="account-form" onSubmit={submit}>
            {mode === 'forgot' && <label>Электронная почта<input name="email" type="email" required maxLength={254} autoComplete="email" /></label>}
            {['verify', 'reset'].includes(mode) && <label>Код из тестового письма
              <input name="token" type="password" required minLength={76} maxLength={76} autoComplete="off"
                value={proof} onChange={event => setProof(event.target.value)} /></label>}
            {mode === 'change' && <label>Текущий пароль<input name="current_password" type="password" required maxLength={128} autoComplete="current-password" /></label>}
            {['reset', 'change'].includes(mode) && <>
              <label>Новый пароль<input name="password" type="password" required minLength={15} maxLength={128} autoComplete="new-password" /></label>
              <label>Повторите новый пароль<input name="confirmation" type="password" required minLength={15} maxLength={128} autoComplete="new-password" /></label>
            </>}
            <button className="primary" disabled={busy} type="submit">{busy ? 'Проверяем…'
              : mode === 'verify' ? 'Подтвердить адрес' : mode === 'forgot' ? 'Запросить восстановление' : 'Сохранить новый пароль'}</button>
          </form>
        </>}
      <p><Link href="/account">Аккаунт</Link> · <Link href="/password/forgot">Забыли пароль?</Link></p>
    </div>
  </section>
}
