import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { components } from '../../shared/api.generated'
import { ApiError, apiRequest } from '../../shared/api'
import { Link } from '../../shell/router'
import '../../shared/ui/records.css'

type Access = components['schemas']['AccessMe']
type Subject = components['schemas']['AccessSubject']
type User = components['schemas']['AdminUser']
type Users = components['schemas']['AdminUsers']
type Receipt = components['schemas']['AccessReceipt']

type Action = 'grant' | 'revoke'

function errorText(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Войдите в серверный аккаунт.'
    if (error.code === 'reauth_required') return 'Текущий пароль не подтверждён.'
    if (error.code === 'delegation_forbidden') return 'Это право нельзя делегировать с вашим текущим лимитом.'
    if (error.code === 'last_access_owner') return 'Нельзя удалить последнего управляющего доступом.'
    if (error.code === 'unmanaged_permission') return 'Право создано вне ACCESS-001 и не изменяется этим экраном.'
    if (error.status === 403) return 'Нет необходимого полномочия управления доступом.'
    if (error.status === 404) return 'Аккаунт или управляемое право не найдено.'
    if (error.status === 409) return 'Состояние изменилось. Обновите карточку и проверьте действие.'
    if (error.status === 422) return 'Проверьте срок, право, номер заявки и идентификатор аккаунта.'
  }
  return 'Результат операции неизвестен. Повторите с теми же данными после проверки состояния.'
}

export function AccessPage() {
  const [access, setAccess] = useState<Access | null>(null)
  const [subject, setSubject] = useState<Subject | null>(null)
  const [query, setQuery] = useState('')
  const [users, setUsers] = useState<User[]>([])
  const [targetId, setTargetId] = useState('')
  const [action, setAction] = useState<Action>('grant')
  const [permission, setPermission] = useState('')
  const [ttl, setTtl] = useState(86400)
  const [caseReference, setCaseReference] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const operation = useRef({ key: '', id: crypto.randomUUID() })

  useEffect(() => {
    const controller = new AbortController()
    setBusy(true); setError('')
    apiRequest<Access>('/api/v1/admin/access/me', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setAccess(value) })
      .catch(reason => { if (!controller.signal.aborted) setError(errorText(reason)) })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [])

  async function loadSubject(id: string, clearReceipt = true) {
    const clean = id.trim()
    if (!/^[0-9a-f-]{36}$/i.test(clean)) { setError('Введите UUID аккаунта.'); return }
    setBusy(true); setError(''); if (clearReceipt) setReceipt(null)
    try {
      const value = await apiRequest<Subject>(`/api/v1/admin/access/subjects/${clean}`)
      setSubject(value); setTargetId(value.id); setPermission('')
    } catch (reason) { setSubject(null); setError(errorText(reason)) }
    finally { setBusy(false) }
  }

  async function search(event: FormEvent) {
    event.preventDefault()
    if (query.trim().length < 3) return
    setBusy(true); setError(''); setUsers([])
    try {
      const params = new URLSearchParams({ q: query.trim(), limit: '20' })
      const value = await apiRequest<Users>('/api/v1/admin/users?' + params)
      setUsers(value.users)
    } catch (reason) { setError(errorText(reason)) }
    finally { setBusy(false) }
  }

  function operationId(key: string) {
    if (operation.current.key !== key) operation.current = { key, id: crypto.randomUUID() }
    return operation.current.id
  }

  const grantOptions = access?.delegation_ceiling ?? []
  const revokeOptions = subject?.permissions.filter(item => item.managed && grantOptions.includes(item.permission)).map(item => item.permission) ?? []
  const options = action === 'grant' ? grantOptions : revokeOptions

  async function mutate(event: FormEvent) {
    event.preventDefault()
    if (!subject || !permission) return
    const key = [action, subject.id, permission, ttl, caseReference.trim().toUpperCase()].join('|')
    const data: Record<string, unknown> = {
      operation_id: operationId(key), permission, scope: 'global',
      case_reference: caseReference.trim(), current_password: password,
    }
    if (action === 'grant') data.ttl_seconds = ttl
    setBusy(true); setError(''); setReceipt(null)
    try {
      const endpoint = `/api/v1/admin/access/subjects/${subject.id}/${action === 'grant' ? 'grants' : 'revocations'}`
      const result = await apiRequest<Receipt>(endpoint, { method: 'POST', data, csrf: access?.csrf_token })
      setReceipt(result); operation.current = { key: '', id: crypto.randomUUID() }
      setCaseReference('')
      await loadSubject(subject.id, false)
    } catch (reason) { setError(errorText(reason)) }
    finally { setPassword(''); setBusy(false) }
  }

  return <section className="admin-page">
    <header className="page-heading"><p className="eyebrow">ACCESS-001 · A-28</p>
      <h1>Доступ персонала</h1>
      <p>Явные серверные права с ограниченным сроком. Этот экран не создаёт роли, wildcard-права или постоянный доступ.</p>
    </header>
    <nav className="admin-links" aria-label="Административные страницы">
      {access?.permissions.includes('users.read_limited') && <Link href="/admin/users">Пользователи</Link>}
      {access?.permissions.includes('audit.read') && <Link href="/admin/audit">Журнал действий</Link>}
      <Link href="/admin/access" aria-current="page">Доступ</Link>
    </nav>
    {error && <p role="alert" className="field-error">{error}</p>}
    {busy && <p role="status">Обновляем серверное состояние…</p>}
    {access && <div className="admin-panel">
      <h2>Найти сотрудника</h2>
      {access.permissions.includes('users.read_limited') && <>
      <form className="admin-search" onSubmit={search}><label>Имя или публичный код
        <input value={query} onChange={e=>setQuery(e.target.value)} minLength={3} maxLength={80} /></label>
        <button disabled={busy || query.trim().length < 3}>Найти</button></form>
      {!!users.length && <div className="admin-table-wrap"><table><thead><tr><th>Имя</th><th>Код</th><th>Действие</th></tr></thead>
        <tbody>{users.map(user=><tr key={user.id}><td>{user.display_name}</td><td>{user.public_code}</td>
          <td><button onClick={()=>void loadSubject(user.id)} disabled={busy}>Управлять доступом</button></td></tr>)}</tbody></table></div>}
      </>}
      <form className="admin-search" onSubmit={e=>{e.preventDefault();void loadSubject(targetId)}}><label>Или UUID аккаунта
        <input aria-label="UUID аккаунта" value={targetId} onChange={e=>setTargetId(e.target.value)} /></label>
        <button disabled={busy || !targetId.trim()}>Открыть</button></form>
    </div>}

    {subject && access && <div className="admin-panel">
      <h2>{subject.display_name}</h2><p>Код: <strong>{subject.public_code}</strong> · scope: <strong>global</strong></p>
      <div className="admin-table-wrap"><table><thead><tr><th>Право</th><th>Срок</th><th>Источник</th></tr></thead>
        <tbody>{subject.permissions.map(item=><tr key={item.permission}><td>{item.permission}</td>
          <td>{item.expires_at ? new Date(item.expires_at*1000).toLocaleString('ru-RU') : 'Без срока'}</td>
          <td>{item.managed ? 'ACCESS-001' : 'Внешнее / bootstrap'}</td></tr>)}</tbody></table></div>
      {!subject.permissions.length && <p>Действующих прав нет.</p>}
      {access.permissions.includes('access.manage') && <form className="admin-form" onSubmit={mutate}>
        <fieldset disabled={busy}><legend>Изменить доступ</legend>
          <label>Действие<select value={action} onChange={e=>{setAction(e.target.value as Action);setPermission('')}}>
            <option value="grant">Выдать</option><option value="revoke">Отозвать</option></select></label>
          <label>Право<select value={permission} onChange={e=>setPermission(e.target.value)} required>
            <option value="">Выберите право</option>{options.map(value=><option key={value} value={value}>{value}</option>)}</select></label>
          {action==='grant' && <label>Срок<select value={ttl} onChange={e=>setTtl(Number(e.target.value))}>
            <option value={3600}>1 час</option><option value={86400}>1 день</option>
            <option value={604800}>7 дней</option><option value={2592000}>30 дней</option></select></label>}
          <label>Номер заявки<input value={caseReference} onChange={e=>setCaseReference(e.target.value)} minLength={3} maxLength={64} required /></label>
          <label>Текущий пароль<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required /></label>
          <button className="primary" disabled={!permission || !caseReference.trim() || !password}>{action==='grant'?'Выдать право':'Отозвать право'}</button>
        </fieldset>
      </form>}
      {receipt && <div className="admin-receipt" role="status"><strong>Операция подтверждена сервером.</strong>
        <p>{receipt.action} · {receipt.permission} · {receipt.case_reference}</p></div>}
    </div>}
  </section>
}
