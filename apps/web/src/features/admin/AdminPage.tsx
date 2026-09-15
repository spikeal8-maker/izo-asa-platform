import { useEffect, useState, type FormEvent } from 'react'
import type { components } from '../../shared/api.generated'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { AdminNav, AuditPanel, UserDetailPanel, UserSearchPanel } from './AdminPanels'
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
  const [href, setHref] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setHref('')
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal })
      .then(value => {
        if (controller.signal.aborted) return
        const permissions = value.account.permissions
        setHref(permissions.includes('users.read_limited') ? '/admin/users' : permissions.includes('access.read') ? '/admin/access' : '')
      }).catch(() => { if (!controller.signal.aborted) setHref('') })
    return () => controller.abort()
  }, [path])
  return href ? <Link href={href} className="staff-link">Администрирование</Link> : null
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
    try { setEvents(await apiRequest<Events>('/api/v1/admin/audit?before=' + events.next_before)) }
    catch (reason) { setError(errorText(reason)) }
    finally { setBusy(false) }
  }
  function refreshCredits() {
    if (!user) return
    void apiRequest<Credits>(`/api/v1/admin/users/${user.id}/credits`).then(setCredits).catch(reason => setError(errorText(reason)))
  }

  const current = auditing ? 'audit' : 'users'
  return <section className="admin-page">
    <header className="page-heading"><p className="eyebrow">АДМИНИСТРИРОВАНИЕ</p>
      <h1>{target ? 'Пользователь' : auditing ? 'Журнал действий' : 'Пользователи'}</h1>
      <p>Управление аккаунтами, балансом и действиями персонала через серверные полномочия.</p></header>
    {!known ? <p role="alert">Этот административный экран ещё не реализован.</p> : <>
      {error && <p role="alert" className="field-error">{error} <button onClick={() => setVersion(value => value + 1)} disabled={busy}>Повторить</button></p>}
      {!access && !busy && <p><Link href="/login">Войти</Link> · <Link href="/verify-email">Подтвердить почту</Link></p>}
      {busy && <p role="status">Загружаем серверные данные…</p>}
      {access && <><AdminNav access={access} current={current} />
        {!target && !auditing && <UserSearchPanel query={query} users={users} busy={busy}
          onQuery={value => { setQuery(value); setUsers(null) }} onSearch={event => void search(event)} onNext={after => void search(undefined, after)} />}
        {user && <UserDetailPanel user={user} credits={credits} access={access} busy={busy} onGranted={refreshCredits} />}
        {events && <AuditPanel events={events} busy={busy} onOlder={() => void older()} />}
      </>}
    </>}
  </section>
}
