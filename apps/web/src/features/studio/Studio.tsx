import { useEffect, useRef, useState } from 'react'
import { Dialog } from '../../shared/ui/Dialog'
import { Icon } from '../../shared/ui/Icon'
import { Link } from '../../shell/router'
import { apiRequest, type AuthView } from '../../shared/api'
import { WorkspaceGate, ResourceState, useResource } from '../../shared/workspace'
import { type Plan, type Credits, type Quote, type Job, problem, navigate } from '../../shared/workspace-api'
import { type Pending, readPending, remember, forget, rejectedBeforeAdmission } from '../../shared/submission'
import './studio.css'

const imageCapabilities = [
  { id: 'test.image.v1', title: 'Пробный режим', detail: 'Знакомство с процессом без внешней AI-модели' },
  { id: 'fal.flux2.klein.4b', title: 'FLUX.2 [klein] 4B', detail: 'AI-генерация изображения' },
]
function Composer({ auth }: { auth: AuthView }) {
  const plan = useResource<Plan>('/api/v1/entitlements')
  const credits = useResource<Credits>('/api/v1/credits')
  const [prompt, setPrompt] = useState('')
  const [size, setSize] = useState('')
  const [capability, setCapability] = useState('')
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
  const capabilities = imageCapabilities.filter(item => plan.data?.policy?.capability_ids.includes(item.id))
  const chosen = sizes.find(item => `${item.width}x${item.height}` === size) ?? sizes[0]
  const chosenCapability = capabilities.find(item => item.id === capability) ?? capabilities[0]
  const permitted = auth.account.email_verified && auth.account.state === 'active'
    && plan.data?.configured && plan.data.policy?.executors.includes('api') && !!chosen && !!chosenCapability
  const canQuote = permitted && !!credits.data && !!prompt.trim() && !busy && !pending && !storageError

  async function estimate() {
    if (!canQuote || active.current || !chosen || !chosenCapability) return
    active.current = true; setBusy(true); setError('')
    try {
      const value = await apiRequest<Quote>('/api/v1/jobs/quotes', { method: 'POST', csrf: auth.csrf_token,
        data: { capability_id: chosenCapability.id, prompt, width: chosen.width, height: chosen.height } })
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
        setQuote(null); setStorageError(true)
        setError('Не удалось сохранить номер запроса. Отправка задания не выполнялась.')
      } else if (rejectedBeforeAdmission(reason)) {
        try { forget(auth.account.id); setPending(null) } catch { setStorageError(true) }
        setError(problem(reason))
      } else {
        setError('Результат отправки пока неизвестен. Повторите тот же запрос или проверьте историю; новое списание не создаётся.')
      }
    } finally { active.current = false; if (alive.current) setBusy(false) }
  }
  return <div className="studio-grid">
    <section className="composer" aria-labelledby="composer-title">
      <div className="panel-heading"><h2 id="composer-title">Что создаём?</h2><Icon name="spark" /></div>
      <ResourceState loading={plan.loading || credits.loading} error={plan.error || credits.error}
        retry={() => { plan.refresh(); credits.refresh() }} />
      {credits.data && <p>Доступно: <strong data-testid="studio-available">{credits.data.balance.available}</strong> баллов.</p>}
      {!auth.account.email_verified && <p className="field-error"><Link href="/verify-email">Подтвердите почту</Link>, чтобы сохранять новые генерации в аккаунте.</p>}
      {plan.data && !permitted && auth.account.email_verified && <p className="field-error">Этот режим сейчас недоступен для вашего аккаунта.</p>}
      {storageError && <p role="alert" className="field-error">Хранилище номера запроса недоступно или повреждено.
        Отправка заблокирована, чтобы не потерять защиту от повторов. <Link href="/jobs">Проверить историю</Link>.</p>}
      {pending && <div className="pending-command" role="status"><strong>Есть незавершённая отправка</strong>
        <p>Сохраняется прежний номер запроса. Не создавайте замену, пока не проверен результат.</p>
        <button className="primary" disabled={busy} onClick={() => void submit()}>Проверить прежний запрос</button>
        <Link href="/jobs">Открыть историю</Link></div>}
      <label className="field-label" htmlFor="prompt">Описание</label>
      <div className="prompt-field"><textarea id="prompt" rows={5} maxLength={2000}
        placeholder="Опишите изображение, стиль, свет и детали…" disabled={busy || !!pending} value={prompt}
        onChange={event => { setPrompt(event.target.value); setQuote(null) }} />
        <span>{prompt.length} / 2000</span></div>
      <label className="field-label" htmlFor="image-capability">Режим</label>
      <select id="image-capability" value={chosenCapability?.id ?? ''} disabled={busy || !!pending}
        onChange={event => { setCapability(event.target.value); setQuote(null) }}>
        {!capabilities.length && <option value="">Нет доступных режимов</option>}
        {capabilities.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select>
      {chosenCapability && <p><strong>{chosenCapability.title}</strong><br /><small>{chosenCapability.detail}</small></p>}
      <label className="field-label" htmlFor="image-size">Размер результата</label>
      <select id="image-size" value={chosen ? `${chosen.width}x${chosen.height}` : ''} disabled={busy || !!pending}
        onChange={event => { setSize(event.target.value); setQuote(null) }}>
        {!sizes.length && <option value="">Нет доступных размеров</option>}
        {sizes.map(item => <option key={`${item.width}x${item.height}`} value={`${item.width}x${item.height}`}>{item.width} × {item.height}</option>)}
      </select>
      {error && <p className="field-error" role="alert">{error}</p>}
      <button className="primary generate-button" disabled={!canQuote} onClick={() => void estimate()}>
        <Icon name="spark" />{busy ? 'Проверяем…' : 'Рассчитать стоимость'}</button>
      <p><Link href="/account/credits">Баланс</Link> · <Link href="/jobs">История</Link></p>
    </section>
    <section className="result-panel"><div className="panel-heading"><h2>Результат</h2></div>
      <div className="server-result-empty"><Icon name="image" /><h3>Здесь появится готовая работа</h3>
        <p>После подтверждения результат сохранится в вашей галерее, откуда его можно открыть и скачать.</p>
        <Link className="secondary" href="/gallery">Открыть галерею</Link></div>
    </section>
    <Dialog open={!!quote} title="Создать изображение?" onClose={() => { if (!busy) setQuote(null) }}>
      {quote && <><p>{quote.test_only ? 'Пробный режим: результат создаётся без внешней AI-модели.' : quote.notice}</p><dl className="summary-list">
        <div><dt>Размер</dt><dd>{quote.width} × {quote.height}</dd></div>
        <div><dt>Баллы для запуска</dt><dd id="quote-reserve">{quote.credits} балл.</dd></div>
        <div><dt>Режим</dt><dd>{quote.test_only ? 'Пробный' : 'AI'}</dd></div></dl>
        <p className="quote-prompt">{quote.prompt}</p>
        {expired && <p role="alert">Расчёт устарел. Закройте окно и повторите.</p>}
        <button className="primary full-width quote-submit" aria-label="Подтвердить создание"
          aria-describedby="quote-reserve" disabled={busy || expired} onClick={() => void submit()}>
          <span>Подтвердить создание</span><small data-testid="quote-submit-price" aria-hidden="true">Резерв: {quote.credits} балл.</small>
        </button></>}
    </Dialog>
  </div>
}
export function Studio() {
  return <><header className="page-heading"><p className="eyebrow">СТУДИЯ / ИЗОБРАЖЕНИЕ</p>
    <h1>Создайте изображение.</h1><p>Опишите идею, выберите режим и формат результата.</p></header>
    <WorkspaceGate>{auth => <Composer auth={auth} />}</WorkspaceGate></>
}
