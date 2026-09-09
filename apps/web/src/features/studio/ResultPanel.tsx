import { useState } from 'react'
import { Icon } from '../../shared/ui/Icon'
import { Dialog } from '../../shared/ui/Dialog'
import { Link } from '../../shell/router'
import { apiRequest, type AuthView } from '../../shared/api'
import { WorkspaceGate, ResourceState, useResource } from '../../shared/workspace'
import { type Job, type Jobs, activeJob, statusName, isId, problem } from '../../shared/workspace-api'
import './studio.css'

const pollJob = (job: Job) => activeJob(job) && job.error_code !== 'reconciliation_required'
const pollJobs = (value: Jobs) => value.jobs.some(pollJob)
function JobList() {
  const [offset, setOffset] = useState(0)
  const { data, error, loading, refresh } = useResource<Jobs>(`/api/v1/jobs?limit=20&offset=${offset}`, pollJobs)
  return <><ResourceState error={error} loading={loading} retry={refresh} />
    {data && <><div className="job-list">{data.jobs.map(job => <Link className="job-card" href={`/jobs/${job.id}`} key={job.id}>
      <strong>{statusName[job.status]}</strong><p>{job.prompt}</p>
      <small>{job.width} × {job.height} · резерв {job.reserved_credits} · списано {job.charged_credits}</small>
    </Link>)}</div>{!data.jobs.length && <section className="gallery-empty"><h2>Заданий пока нет</h2>
      <p>В списке только задания вашего серверного аккаунта.</p><Link className="primary" href="/image">Открыть студию</Link></section>}
      <div className="workspace-actions">{offset > 0 && <button onClick={() => setOffset(Math.max(0, offset - 20))}>Предыдущие задания</button>}
        {data.next_offset !== null && <button onClick={() => setOffset(data.next_offset!)}>Следующие задания</button>}
        <button onClick={refresh}>Обновить задания</button></div></>}
  </>
}
function JobDetail({ id, auth }: { id: string; auth: AuthView }) {
  const result = useResource<Job>(`/api/v1/jobs/${id}`, pollJob)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const job = result.data
  async function cancel() {
    if (busy) return
    setBusy(true); setError('')
    try {
      await apiRequest<Job>(`/api/v1/jobs/${id}/cancel`, { method: 'POST', csrf: auth.csrf_token })
      setConfirm(false); result.refresh()
    } catch (reason) { setError(problem(reason)); result.refresh() }
    finally { setBusy(false) }
  }
  return <><Link className="back-link" href="/jobs"><Icon name="back" /> Все задания</Link>
    <ResourceState error={result.error} loading={result.loading} retry={result.refresh} />
    {job && <section className="composer job-record"><h2 data-testid="job-status">{statusName[job.status]}</h2>
      <p className="job-prompt">{job.prompt}</p><p>Тестовый исполнитель · не AI-генерация.</p>
      <dl className="summary-list"><div><dt>Размер</dt><dd>{job.width} × {job.height}</dd></div>
        <div><dt>Резерв</dt><dd>{job.reserved_credits}</dd></div><div><dt>Списано</dt><dd data-testid="job-charged">{job.charged_credits}</dd></div>
        <div><dt>Попыток</dt><dd>{job.attempt_count}</dd></div></dl>
      {activeJob(job) && <p>Страница может быть закрыта: состояние хранится на сервере. Процент выполнения не выдумывается.</p>}
      {job.error_code && <p role="status">{job.error_code === 'reconciliation_required'
        ? 'Нужен разбор оператором. Резерв сохранён.'
        : job.status === 'reconciling' ? 'Проверяем уже записанный файл. Новое задание не требуется.'
        : 'Задание не завершено успешно. Проверьте баланс перед новым запуском.'}</p>}
      {job.cancel_requested && <p>Запрос отмены принят. Окончательный результат определяется сервером.</p>}
      <div className="workspace-actions">{job.status === 'succeeded' && job.asset_id && <Link className="primary" href={`/gallery/${job.asset_id}`}>Открыть работу</Link>}
        {activeJob(job) && !job.cancel_requested && <button className="secondary" onClick={() => setConfirm(true)}>Отменить задание</button>}
        <button onClick={result.refresh} disabled={busy}>Обновить задание</button>
        <Link href="/account/credits">Проверить баланс</Link></div>
    </section>}
    {error && <p className="field-error" role="alert">{error}</p>}
    <Dialog open={confirm} title="Отменить задание?" onClose={() => { if (!busy) setConfirm(false) }}>
      <p>До сохранения результата сервер может освободить резерв. Если запись уже началась, отмена — запрос, а не обещание возврата.</p>
      <button className="primary" disabled={busy} onClick={() => void cancel()}>Подтвердить отмену</button>
    </Dialog></>
}
export function ResultPanel({ id }: { id?: string }) {
  return <><header className="page-heading"><p className="eyebrow">СЕРВЕРНЫЙ ПРОЦЕСС</p><h1>{id ? 'Задание' : 'Задания'}</h1>
    <p>Состояние, результат и расход принадлежат вашему аккаунту, а не этой вкладке.</p></header>
    {id && !isId(id) ? <section className="gallery-empty"><h2>Задание не найдено</h2><Link href="/jobs">Все задания</Link></section>
      : <WorkspaceGate>{auth => id ? <JobDetail key={id} id={id} auth={auth} /> : <JobList />}</WorkspaceGate>}
  </>
}
