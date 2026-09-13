import { useEffect, useRef, useState } from 'react'
import { apiImage, apiRequest, ApiError, type GuestView } from '../../shared/api'
import { type Asset, type Job, type Jobs, type Quote, activeJob, problem } from '../../shared/workspace-api'
import { Link } from '../../shell/router'
import { Icon } from '../../shared/ui/Icon'

const CAPABILITY = 'test.image.v1'
const SIZE = 512

const guestMessages: Record<string, string> = {
  guest_disabled: 'Пробный режим сейчас недоступен.',
  guest_rate_limited: 'Пробный лимит для этого подключения уже использован. Создайте аккаунт, чтобы продолжить.',
  guest_trial_used: 'Пробная работа уже создана. Создайте аккаунт, чтобы продолжить.',
  guest_capability_restricted: 'Этот режим доступен после регистрации.',
  guest_required: 'Пробная сессия завершилась. Начните новую или создайте аккаунт.',
}

function guestProblem(reason: unknown) {
  return reason instanceof ApiError && guestMessages[reason.code]
    ? guestMessages[reason.code] : problem(reason)
}

export function GuestTrial() {
  const [guest, setGuest] = useState<GuestView | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [imageUrl, setImageUrl] = useState('')
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    const controller = new AbortController()
    apiRequest<GuestView>('/api/v1/guest/me', { signal: controller.signal }).then(async value => {
      if (controller.signal.aborted) return
      setGuest(value)
      const history = await apiRequest<Jobs>('/api/v1/guest/jobs', { signal: controller.signal })
      if (!controller.signal.aborted) setJob(history.jobs[0] ?? null)
    }).catch(reason => {
      if (!controller.signal.aborted && !(reason instanceof ApiError && reason.status === 401))
        setError(guestProblem(reason))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => { alive.current = false; controller.abort() }
  }, [])

  useEffect(() => {
    if (!job || !activeJob(job)) return
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const next = await apiRequest<Job>(`/api/v1/guest/jobs/${job.id}`, { signal: controller.signal })
        if (!controller.signal.aborted) setJob(next)
      } catch (reason) {
        if (!controller.signal.aborted) setError(guestProblem(reason))
      }
    }, 1500)
    return () => { clearTimeout(timer); controller.abort() }
  }, [job])

  useEffect(() => {
    if (job?.status !== 'succeeded' || !job.asset_id) return
    const controller = new AbortController()
    let url = ''
    void (async () => {
      try {
        const asset = await apiRequest<Asset>(`/api/v1/guest/assets/${job.asset_id}`, { signal: controller.signal })
        const blob = await apiImage(`/api/v1/guest/assets/${asset.id}/content`, asset.byte_size, asset.sha256,
          controller.signal)
        if (!controller.signal.aborted) { url = URL.createObjectURL(blob); setImageUrl(url) }
      } catch (reason) { if (!controller.signal.aborted) setError(guestProblem(reason)) }
    })()
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [job?.status, job?.asset_id])

  async function ensureGuest(): Promise<GuestView> {
    if (guest) return guest
    const value = await apiRequest<GuestView>('/api/v1/guest/start', { method: 'POST', data: {} })
    if (alive.current) setGuest(value)
    return value
  }

  async function generate() {
    if (!prompt.trim() || busy || job) return
    setBusy(true); setError('')
    try {
      const current = await ensureGuest()
      const quote = await apiRequest<Quote>('/api/v1/guest/quotes', { method: 'POST', csrf: current.csrf_token,
        data: { capability_id: CAPABILITY, prompt: prompt.trim(), width: SIZE, height: SIZE } })
      const created = await apiRequest<Job>('/api/v1/guest/jobs', { method: 'POST', csrf: current.csrf_token,
        data: { quote_id: quote.id, operation_id: crypto.randomUUID() } })
      if (alive.current) setJob(created)
    } catch (reason) { if (alive.current) setError(guestProblem(reason)) }
    finally { if (alive.current) setBusy(false) }
  }

  const finished = job && !activeJob(job)
  return <div className="studio-grid" data-testid="guest-trial">
    <section className="composer" aria-labelledby="guest-title">
      <div className="panel-heading"><h2 id="guest-title">Попробуйте без регистрации</h2><Icon name="spark" /></div>
      <p>Создайте одну пробную работу. Регистрация понадобится только для продолжения и сохранения истории между устройствами.</p>
      <label className="field-label" htmlFor="guest-prompt">Описание</label>
      <div className="prompt-field"><textarea id="guest-prompt" rows={5} maxLength={2000}
        placeholder="Например: стеклянный город на рассвете, мягкий свет…" disabled={busy || !!job}
        value={prompt} onChange={event => setPrompt(event.target.value)} /><span>{prompt.length} / 2000</span></div>
      <p><small>Пробный результат: {SIZE} × {SIZE}. Внешний AI-провайдер в этом режиме не вызывается.</small></p>
      {loading && <p role="status">Проверяем пробный доступ…</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      {!job && <button className="primary generate-button" disabled={loading || busy || !prompt.trim()}
        onClick={() => void generate()}><Icon name="spark" />{busy ? 'Создаём…' : 'Создать пробную работу'}</button>}
      {job && activeJob(job) && <p role="status">Создаём работу…</p>}
      {finished && <div className="pending-command"><strong>Хотите продолжить?</strong>
        <p>Создайте аккаунт — эта пробная работа останется вашей.</p>
        <Link className="primary" href="/register">Создать аккаунт</Link>
        <Link href="/login">Уже есть аккаунт? Войти</Link></div>}
    </section>
    <section className="result-panel"><div className="panel-heading"><h2>Результат</h2></div>
      {imageUrl ? <img src={imageUrl} alt="Пробная работа" className="result-image" />
        : <div className="server-result-empty"><Icon name="image" /><h3>{job?.status === 'failed' ? 'Не удалось создать работу' : 'Здесь появится пробная работа'}</h3>
          <p>{job ? 'Сервер сохраняет результат за этой гостевой сессией.' : 'Опишите идею и запустите один пробный результат.'}</p></div>}
    </section>
  </div>
}
