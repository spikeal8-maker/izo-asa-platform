import type { FormEvent } from 'react'
import type { components } from '../../shared/api.generated'
import { Link } from '../../shell/router'
import { GrantForm } from './GrantForm'

type Access = components['schemas']['AdminAccess']
type User = components['schemas']['AdminUser']
type Users = components['schemas']['AdminUsers']
type Credits = components['schemas']['Overview']
type Events = components['schemas']['AdminEvents']

export function AdminNav({ access, current }: { access: Access; current: 'users' | 'audit' | 'access' }) {
  return <nav className="admin-links" aria-label="Административные страницы">
    <Link href="/admin/users" aria-current={current === 'users' ? 'page' : undefined}>Пользователи</Link>
    {access.permissions.includes('audit.read') && <Link href="/admin/audit" aria-current={current === 'audit' ? 'page' : undefined}>Журнал действий</Link>}
    {access.permissions.includes('access.read') && <Link href="/admin/access" aria-current={current === 'access' ? 'page' : undefined}>Доступ</Link>}
    <Link href="/account/credits">Мои баллы</Link>
  </nav>
}

export function UserSearchPanel({ query, users, busy, onQuery, onSearch, onNext }: {
  query: string
  users: Users | null
  busy: boolean
  onQuery: (value: string) => void
  onSearch: (event: FormEvent<HTMLFormElement>) => void
  onNext: (after: string) => void
}) {
  return <div className="admin-panel admin-panel-flat">
    <form onSubmit={onSearch} className="admin-search"><label>Имя или публичный код
      <input value={query} onChange={event => onQuery(event.target.value)} minLength={3} maxLength={80} required /></label>
      <button className="primary" disabled={busy}>Найти пользователя</button></form>
    {!users && !busy && <p>Введите минимум 3 символа. Список не загружается целиком.</p>}
    {users && <><div className="admin-table-wrap"><table><thead><tr><th>Имя</th><th>Код</th><th>Статус</th><th>Действие</th></tr></thead>
      <tbody>{users.users.map(item => <tr key={item.id}><td>{item.display_name}</td><td>{item.public_code}</td><td>{item.state}</td>
        <td><Link href={'/admin/users/' + item.id}>Открыть карточку</Link></td></tr>)}</tbody></table></div>
      {users.users.length === 0 && <p>Совпадений нет.</p>}
      {users.next_after && <button disabled={busy} onClick={() => onNext(users.next_after!)}>Следующие пользователи</button>}</>}
  </div>
}

export function UserDetailPanel({ user, credits, access, busy, onGranted }: {
  user: User
  credits: Credits | null
  access: Access
  busy: boolean
  onGranted: () => void
}) {
  return <div className="admin-panel admin-user-card admin-user-detail">
    <div className="admin-card-heading"><div><small>Пользователь</small><h2>{user.display_name}</h2></div><span>{user.state}</span></div>
    <dl className="summary-list"><div><dt>Публичный код</dt><dd>{user.public_code}</dd></div>
      <div><dt>Способ входа подтверждён</dt><dd>{user.verified ? 'Да' : 'Нет'}</dd></div></dl>
    {credits ? <><div className="admin-section-heading"><h2>Серверный баланс</h2><span data-testid="admin-available">{credits.balance.available}</span></div>
      <dl className="summary-list"><div><dt>Доступно</dt><dd>{credits.balance.available}</dd></div><div><dt>В резерве</dt><dd>{credits.balance.reserved}</dd></div></dl>
      <h3>Последние операции</h3><ul className="admin-history">{credits.entries.map(entry => <li key={entry.entry_id}>
        <span>{entry.kind} · {entry.reason}</span><strong>{entry.balance_delta > 0 ? '+' : ''}{entry.balance_delta}</strong></li>)}</ul>
      {!credits.entries.length && <p>Операций пока нет.</p>}
      {credits.next_before && <p>Показаны последние 20 операций. Полный поиск журнала будет отдельной поверхностью.</p>}</>
      : !busy && <p>Финансовые сведения не загружены или нет полномочия на их просмотр.</p>}
    {access.max_grant > 0 && access.permissions.includes('credits.grant') &&
      <GrantForm user={user} maximum={access.max_grant} csrf={access.csrf_token} onGranted={onGranted} />}
  </div>
}

export function AuditPanel({ events, busy, onOlder }: { events: Events; busy: boolean; onOlder: () => void }) {
  return <div className="admin-panel admin-panel-flat"><div className="admin-section-heading"><div><small>Аудит</small><h2>Последние действия персонала</h2></div></div>
    <p>События не редактируются. Приватные файлы, пароли и ключи здесь не отображаются.</p>
    <ul className="admin-history">{events.events.map(item => <li key={item.id}><div><strong>{item.action}</strong>
      <p>{item.outcome} · {new Date(item.created_at * 1000).toLocaleString('ru-RU')}{item.case_reference ? ' · ' + item.case_reference : ''}</p></div>
      {item.target_id && <Link href={'/admin/users/' + item.target_id}>Получатель</Link>}</li>)}</ul>
    {!events.events.length && <p>Событий нет.</p>}{events.next_before && <button disabled={busy} onClick={onOlder}>Более ранние события</button>}
  </div>
}
