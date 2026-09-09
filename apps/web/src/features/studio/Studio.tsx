import { useEffect, useRef, useState } from 'react'
import { Dialog } from '../../shared/ui/Dialog'
import { Icon, type IconName } from '../../shared/ui/Icon'
import { Link } from '../../shell/router'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import { WorkspaceGate, ResourceState, useResource } from '../../shared/workspace'
import { type Plan, type Credits, type Quote, type Job, problem, navigate } from '../../shared/workspace-api'
import { type Pending, readPending, remember, forget } from '../../shared/submission'
import './studio.css'

const directions: { title: string; href: string; icon: IconName }[] = [
  { title: 'Изображение', href: '/image', icon: 'image' },
  { title: 'Видео', href: '/studio/video', icon: 'video' },
  { title: 'Звук', href: '/studio/audio', icon: 'audio' },
  { title: '3D', href: '/studio/3d', icon: 'cube' },
  { title: 'Чат', href: '/studio/chat', icon: 'chat' },
]
const deniedBeforeAdmission = new Set(['quote_expired', 'invalid_input', 'insufficient_credits',
  'plan_unconfigured', 'plan_restricted', 'storage_quota_exceeded', 'concurrency_limit',
  'rate_limited', 'feature_unavailable', 'jobs_disabled', 'verification_required', 'account_restricted'])

function Composer({ auth }: { auth: AuthView }) {
  const plan = useResource<Plan>('/api/v1/entitlements')
  const credits = useResource<Credits>('/api/v1/credits')
  const [prompt, setPrompt] = useState('')
  const [size, setSize] = useState('')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [expired, setExpired] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const [storageError, setStorageError] = useState(false)
  const active = useRef(false)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    try { setPending(readPending(auth.account.id)) } catch { setStorageError(true) }
    return () => { alive.current = false }
  }, [auth.account.id])
  useEffect(() => {
    setExpired(!!quote && quote.expires_at * 1000 <= Date.now())
    if (!quote) return
    const timer = setTimeout(() => setExpired(true), Math.max(0, quote.expires_at * 1000 - Date.now()))
    return () => clearTimeout(timer)
  }, [quote])
  const sizes = plan.data?.policy?.image_sizes.filter(item => item.width >= 32 && item.width <= 512
    && item.height >= 32 && item.height <= 512) ?? []
  const chosen = sizes.find(item => `${item.width}x${item.height}` === size) ?? sizes[0]
  const permitted = auth.account.email_verified && auth.account.state === 'active'
    && plan.data?.configured && plan.data.policy?.capability_ids.includes('test.image.v1')
    && plan.data.policy.executors.includes('api') && !!chosen
  const canQuote = permitted && !!credits.data && !!prompt.trim() && !busy && !pending && !storageError

  async function estimate() {
    if (!canQuote || active.current || !chosen) return
    active.current = true; setBusy(true); setError('')
    try {
      const value = await apiRequest<Quote>('/api/v1/jobs/quotes', { method: 'POST', csrf: auth.csrf_token,
        data: { capability_id: 'test.image.v1', prompt, width: chosen.width, height: chosen.height } })
      if (alive.current) setQuote(value)
    } catch (reason) { if (alive.current) setError(problem(reason)) }
    finally { active.current = false; if (alive.current) setBusy(false) }
  }
  async function submit() {
    if (active.current || (!pending && (!quote || expired))) return
    active.current = true; setBusy(true); setError('')
    let command: Pending | null = pending
    try {
      command = pending ?? remember(auth.account.id, quote!.id)
      setPending(command); setQuote(null)
      const value = await apiRequest<Job>('/api/v1/jobs', { method: 'POST', csrf: auth.csrf_token,
        data: { quote_id: command.quote_id, operation_id: command.operation_id } })
      try { forget(auth.account.id) } catch { /* A surviving ID only replays this receipt. */ }
      if (alive.current) { setPending(null); navigate(`/jobs/${value.id}`) }
    } catch (reason) {
      if (!alive.current) return
      if (!command) {
        setStorageError(true)
        setError('Не удалось сохранить номер запроса. Отправка задания не выполнялась.')
      } else if (reason instanceof ApiError && deniedBeforeAdmission.has(reason.code)) {
        try { forget(auth.account.id); setPending(null) } catch { setStorageError(true) }
        setError(problem(reason))
      } else {
        setError('Результат отправки пока неизвестен. Повторите тот же запрос или проверьте задания; новое списание не создаётся.')
      }
    } finally { active.current = false; if (alive.current) setBusy(false) }
  }
  return <div className="studio-grid">
    <section className="composer" aria-labelledby="composer-title">
      <div className="panel-heading"><h2 id="composer-title">Что создаём?</h2><Icon name="spark" /></div>
      <ResourceState loading={plan.loading || credits.loading} error={plan.error || credits.error}
        retry={() => { plan.refresh(); credits.refresh() }} />
      {credits.data && <p>Доступно на сервере: <strong data-testid="studio-available">{credits.data.balance.available}</strong> баллов.
        В резерве: {credits.data.balance.reserved}.</p>}
      {!auth.account.email_verified && <p className="field-error"><Link href="/verify-email">Подтвердите почту</Link> перед созданием задания.</p>}
      {plan.data && !permitted && auth.account.email_verified && <p className="field-error">Оператор должен разрешить тестовый исполнитель и размеры в вашем плане.</p>}
      {storageError && <p role="alert" className="field-error">Хранилище номера запроса недоступно или повреждено.
        Отправка заблокирована, чтобы не потерять защиту от повторов. <Link href="/jobs">Проверить задания</Link>.</p>}
      {pending && <div className="pending-command" role="status">
        <strong>Есть незавершённое подтверждение</strong>
        <p>Сохраняется прежний номер запроса. Не создавайте замену, пока не проверен результат.</p>
        <button className="primary" disabled={busy} onClick={() => void submit()}>Проверить прежний запрос</button>
        <Link href="/jobs">Открыть задания</Link>
      </div>}
      <label className="field-label" htmlFor="prompt">Описание</label>
      <div className="prompt-field"><textarea id="prompt" rows={5} maxLength={2000}
        placeholder="Опишите задачу…" disabled={busy || !!pending} value={prompt}
        onChange={event => { setPrompt(event.target.value); setQuote(null) }} />
        <span>{prompt.length} / 2000</span></div>
      <p className="field-label">Исполнитель</p>
      <p><strong>Диагностическое изображение</strong><br /><small>test.image.v1 · не нейросеть</small></p>
      <label className="field-label" htmlFor="image-size">Размер результата</label>
      <select id="image-size" value={chosen ? `${chosen.width}x${chosen.height}` : ''} disabled={busy || !!pending}
        onChange={event => { setSize(event.target.value); setQuote(null) }}>
        {!sizes.length && <option value="">Нет доступных размеров</option>}
        {sizes.map(item => <option key={`${item.width}x${item.height}`} value={`${item.width}x${item.height}`}>
          {item.width} × {item.height}</option>)}
      </select>
      <p>Исходники, редактирование и другие модели пока не подключены. Разрешение вашего экрана не меняет размер файла.</p>
      {error && <p className="field-error" role="alert">{error}</p>}
      <button className="primary generate-button" disabled={!canQuote} onClick={() => void estimate()}>
        <Icon name="spark" />{busy ? 'Проверяем…' : 'Рассчитать стоимость'}</button>
      <p><Link href="/account/credits">Баланс и история</Link> · <Link href="/jobs">Мои задания</Link></p>
    </section>
    <section className="result-panel"><div className="panel-heading"><h2>От запроса к сохранённой работе</h2></div>
      <div className="server-result-empty"><Icon name="image" /><h3>Результат создаётся на сервере</h3>
        <p>Подтвердите цену. Задание сохранится в базе и будет выполнено отдельным процессом, даже после закрытия страницы.</p>
        <p>Сейчас создаётся диагностический PNG с отметкой TEST ONLY. Реальные AI-модели ещё не подключены.</p>
        <Link className="secondary" href="/gallery">Открыть мою галерею</Link></div>
    </section>
    <Dialog open={!!quote} title="Подтвердить серверное задание?" onClose={() => { if (!busy) setQuote(null) }}>
      {quote && <><p>{quote.notice}</p><dl className="summary-list">
        <div><dt>Размер файла</dt><dd>{quote.width} × {quote.height}</dd></div>
        <div><dt>Серверный резерв</dt><dd>{quote.credits} балл.</dd></div>
        <div><dt>Реальный AI-вызов</dt><dd>Нет</dd></div></dl>
        <p className="quote-prompt">{quote.prompt}</p>
        {expired && <p role="alert">Цена устарела. Закройте окно и рассчитайте её заново.</p>}
        <button className="primary full-width" disabled={busy || expired} onClick={() => void submit()}>Подтвердить создание</button></>}
    </Dialog>
  </div>
}
export function Studio() {
  return <><header className="page-heading"><p className="eyebrow">СТУДИЯ / СЕРВЕР</p>
    <h1>Ваша идея. <span>Новая форма.</span></h1><p>Задания и результаты сохраняются в вашем аккаунте.</p></header>
    <div className="direction-tabs" aria-label="Направления творчества">{directions.map((item, index) =>
      <Link key={item.href} href={item.href} className={`workspace-card ${index === 0 ? 'selected' : ''}`}
        aria-current={index === 0 ? 'page' : undefined}><Icon name={item.icon} />{item.title}
        {index > 0 && <span className="direction-soon">позже</span>}</Link>)}</div>
    <WorkspaceGate>{auth => <Composer auth={auth} />}</WorkspaceGate></>
}
