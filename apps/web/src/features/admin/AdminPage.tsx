import { useEffect, useState, type FormEvent } from 'react'
import type { components } from '../../shared/api.generated'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { GrantForm } from './GrantForm'
import '../../shared/ui/records.css'

type Access = components['schemas']['AdminAccess']
type User = components['schemas']['AdminUser']
type Users = components['schemas']['AdminUsers']
type Credits = components['schemas']['Overview']
type Events = components['schemas']['AdminEvents']

function errorText(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Войдите в серверный аккаунт.'
    if (error.code === 'verification_required') return 'Подтвердите почту административного аккаунта.'
    if (error.status === 403) return 'Нет необходимого административного полномочия.'
    if (error.status === 404) return 'Пользователь не найден.'
    if (error.status === 422) return 'Проверьте строку поиска или адрес страницы.'
  }
  return 'Не удалось получить данные сервера. Повторите запрос; демонстрационные сведения не подставляются.'
}

export function AdminLink({ path }: { path: string }) {
  const [allowed, setAllowed] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    setAllowed(false)
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setAllowed(value.account.permissions.includes('users.read_limited')) })
      .catch(() => { if (!controller.signal.aborted) setAllowed(false) })
    return () => controller.abort()
  }, [path])
  return allowed ? <Link href="/admin/users" className="staff-link">Администрирование</Link> : null
}

export function AdminPage({ path }: { path: string }) {
  const [access, setAccess] = useState<Access | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [credits, setCredits] = useState<Credits | null>(null)
  const [events, setEvents] = useState<Events | null>(null)
  const [users, setUsers] = useState<Users | null>(null)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  const match = /^\/admin\/users\/([0-9a-f-]{36})$/i.exec(path)
  const target = match?.[1]
  const auditing = path === '/admin/audit'
  const known = !!target || ['/admin', '/admin/users', '/admin/audit'].includes(path)

  useEffect(() => {
    const controller = new AbortController()
    setBusy(true); setError(''); setAccess(null); setUser(null); setCredits(null); setEvents(null)
    async function load() {
      const value = await apiRequest<Access>('/api/v1/admin/me', { signal: controller.signal })
      if (controller.signal.aborted) return
      setAccess(value)
      if (target) {
        const card = await apiRequest<User>(`/api/v1/admin/users/${target}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        setUser(card)
        if (value.permissions.includes('credits.read')) {
          const result = await apiRequest<Credits>(`/api/v1/admin/users/${target}/credits`, { signal: controller.signal })
          if (!controller.signal.aborted) setCredits(result)
        }
      } else if (auditing) {
        const result = await apiRequest<Events>('/api/v1/admin/audit', { signal: controller.signal })
        if (!controller.signal.aborted) setEvents(result)
      }
    }
    if (known) void load().catch(reason => { if (!controller.signal.aborted) setError(errorText(reason)) })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    else setBusy(false)
    return () => controller.abort()
  }, [target, auditing, known, version])

  async function search(event?: FormEvent, after?: string) {
    event?.preventDefault()
    if (busy || query.trim().length < 3) return
    setBusy(true); setError('')
    try {
      const params = new URLSearchParams({ q: query.trim(), limit: '20' })
      if (after) params.set('after', after)
      setUsers(await apiRequest<Users>('/api/v1/admin/users?' + params))
    } catch (reason) { setError(errorText(reason)); setUsers(null) }
    finally { setBusy(false) }
  }
  async function older() {
    if (busy || !events?.next_before) return
    setBusy(true)
    try { setEvents(await apiRequest<Events>('/api/v1/admin/audit?before='+events.next_before)) }
    catch (reason) { setError(errorText(reason)) }
    finally { setBusy(false) }
  }

  return <section className="admin-page">
    <header className="page-heading"><p className="eyebrow">СЕРВЕРНОЕ УПРАВЛЕНИЕ · ADMIN-001</p>
      <h1>{target ? 'Пользователь' : auditing ? 'Журнал действий' : 'Пользователи'}</h1>
      <p>Настоящие аккаунты и баллы. Студия и её демо-работы к этому балансу ещё не подключены.</p>
    </header>
    {!known ? <p role="alert">Этот административный экран ещё не реализован.</p> : <>
      {error && <p role="alert" className="field-error">{error} <button onClick={() => setVersion(v=>v+1)} disabled={busy}>Повторить</button></p>}
      {!access && !busy && <p><Link href="/login">Войти</Link> · <Link href="/verify-email">Подтвердить почту</Link></p>}
      {busy && <p role="status">Загружаем серверные данные…</p>}
      {access && <>
        <nav className="admin-links" aria-label="Административные страницы">
          <Link href="/admin/users">Пользователи</Link>
          {access.permissions.includes('audit.read') && <Link href="/admin/audit">Журнал действий</Link>}
          <Link href="/account/credits">Мои баллы</Link>
        </nav>
        {!target && !auditing && <div className="admin-panel">
          <form onSubmit={search} className="admin-search"><label>Имя или публичный код
            <input value={query} onChange={e=>{setQuery(e.target.value);setUsers(null)}} minLength={3} maxLength={80} required /></label>
            <button className="primary" disabled={busy}>Найти пользователя</button></form>
          {!users && !busy && <p>Введите минимум 3 символа. Список не загружается целиком.</p>}
          {users && <><div className="admin-table-wrap"><table><thead><tr><th>Имя</th><th>Код</th><th>Статус</th><th>Действие</th></tr></thead>
            <tbody>{users.users.map(item=><tr key={item.id}><td>{item.display_name}</td><td>{item.public_code}</td><td>{item.state}</td>
              <td><Link href={'/admin/users/'+item.id}>Открыть карточку</Link></td></tr>)}</tbody></table></div>
            {users.users.length===0 && <p>Совпадений нет.</p>}
            {users.next_after && <button disabled={busy} onClick={()=>void search(undefined,users.next_after!)}>Следующие пользователи</button>}</>}
        </div>}
        {user && <div className="admin-panel"><h2>{user.display_name}</h2>
          <dl className="summary-list"><div><dt>Публичный код</dt><dd>{user.public_code}</dd></div>
            <div><dt>Состояние</dt><dd>{user.state}</dd></div><div><dt>Способ входа подтверждён</dt><dd>{user.verified?'Да':'Нет'}</dd></div></dl>
          {credits ? <><h2>Серверный баланс</h2><dl className="summary-list">
            <div><dt>Доступно</dt><dd data-testid="admin-available">{credits.balance.available}</dd></div>
            <div><dt>В резерве</dt><dd>{credits.balance.reserved}</dd></div></dl>
            <h3>Последние операции</h3><ul className="admin-history">{credits.entries.map(entry=><li key={entry.entry_id}>
              <span>{entry.kind} · {entry.reason}</span><strong>{entry.balance_delta>0?'+':''}{entry.balance_delta}</strong></li>)}</ul>
            {!credits.entries.length && <p>Операций пока нет.</p>}
            {credits.next_before && <p>Показаны последние 20 операций. Полный поиск журнала — следующий интерфейсный пакет.</p>}</>
            : !busy && <p>Финансовые сведения не загружены или нет полномочия на их просмотр.</p>}
          {access.max_grant>0 && access.permissions.includes('credits.grant') &&
            <GrantForm user={user} maximum={access.max_grant} csrf={access.csrf_token}
              onGranted={()=>{void apiRequest<Credits>(`/api/v1/admin/users/${user.id}/credits`).then(setCredits).catch(reason=>setError(errorText(reason)))}} />}
        </div>}
        {events && <div className="admin-panel"><h2>Последние действия персонала</h2>
          <p>События не редактируются. Приватные файлы, пароли и ключи здесь не отображаются.</p>
          <ul className="admin-history">{events.events.map(item=><li key={item.id}><div><strong>{item.action}</strong>
            <p>{item.outcome} · {new Date(item.created_at*1000).toLocaleString('ru-RU')}{item.case_reference?' · '+item.case_reference:''}</p></div>
            {item.target_id && <Link href={'/admin/users/'+item.target_id}>Получатель</Link>}</li>)}</ul>
          {!events.events.length && <p>Событий нет.</p>}{events.next_before && <button disabled={busy} onClick={()=>void older()}>Более ранние события</button>}
        </div>}
      </>}
    </>}
  </section>
}
