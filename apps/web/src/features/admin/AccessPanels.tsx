import type { FormEventHandler } from 'react'
import type { components } from '../../shared/api.generated'

type Access = components['schemas']['AccessMe']
type Subject = components['schemas']['AccessSubject']
type User = components['schemas']['AdminUser']
type Receipt = components['schemas']['AccessReceipt']
type Action = 'grant' | 'revoke'

export function AccessLookupPanel({ access, query, users, targetId, busy, onQuery, onTarget, onSearch, onOpenUser, onOpenTarget }: {
  access: Access
  query: string
  users: User[]
  targetId: string
  busy: boolean
  onQuery: (value: string) => void
  onTarget: (value: string) => void
  onSearch: FormEventHandler<HTMLFormElement>
  onOpenUser: (id: string) => void
  onOpenTarget: FormEventHandler<HTMLFormElement>
}) {
  return <div className="admin-panel admin-panel-flat">
    <div className="admin-section-heading"><div><small>Сотрудник</small><h2>Найти аккаунт</h2></div></div>
    {access.permissions.includes('users.read_limited') && <><form className="admin-search" onSubmit={onSearch}><label>Имя или публичный код
      <input value={query} onChange={event => onQuery(event.target.value)} minLength={3} maxLength={80} /></label>
      <button disabled={busy || query.trim().length < 3}>Найти</button></form>
      {!!users.length && <div className="admin-table-wrap"><table><thead><tr><th>Имя</th><th>Код</th><th>Действие</th></tr></thead>
        <tbody>{users.map(user => <tr key={user.id}><td>{user.display_name}</td><td>{user.public_code}</td>
          <td><button onClick={() => onOpenUser(user.id)} disabled={busy}>Управлять доступом</button></td></tr>)}</tbody></table></div>}</>}
    <form className="admin-search" onSubmit={onOpenTarget}><label>Или UUID аккаунта
      <input aria-label="UUID аккаунта" value={targetId} onChange={event => onTarget(event.target.value)} /></label>
      <button disabled={busy || !targetId.trim()}>Открыть</button></form>
  </div>
}

export function AccessSubjectPanel({ subject, access, action, permission, ttl, caseReference, password, busy, receipt, options,
  onAction, onPermission, onTtl, onCaseReference, onPassword, onMutate }: {
  subject: Subject
  access: Access
  action: Action
  permission: string
  ttl: number
  caseReference: string
  password: string
  busy: boolean
  receipt: Receipt | null
  options: string[]
  onAction: (value: Action) => void
  onPermission: (value: string) => void
  onTtl: (value: number) => void
  onCaseReference: (value: string) => void
  onPassword: (value: string) => void
  onMutate: FormEventHandler<HTMLFormElement>
}) {
  return <div className="admin-panel admin-user-card access-subject-panel">
    <div className="admin-card-heading"><div><small>Доступ</small><h2>{subject.display_name}</h2></div><span>{subject.public_code}</span></div>
    <div className="admin-table-wrap"><table><thead><tr><th>Право</th><th>Срок</th><th>Источник</th></tr></thead>
      <tbody>{subject.permissions.map(item => <tr key={item.permission}><td>{item.permission}</td>
        <td>{item.expires_at ? new Date(item.expires_at * 1000).toLocaleString('ru-RU') : 'Без срока'}</td>
        <td>{item.managed ? 'ACCESS-001' : 'Внешнее / bootstrap'}</td></tr>)}</tbody></table></div>
    {!subject.permissions.length && <p>Действующих прав нет.</p>}
    <p className="prototype-note">scope: <strong>global</strong></p>
    {access.permissions.includes('access.manage') && <form className="admin-form" onSubmit={onMutate}>
      <fieldset disabled={busy}><legend>Изменить доступ</legend>
        <label>Действие<select value={action} onChange={event => onAction(event.target.value as Action)}>
          <option value="grant">Выдать</option><option value="revoke">Отозвать</option></select></label>
        <label>Право<select value={permission} onChange={event => onPermission(event.target.value)} required>
          <option value="">Выберите право</option>{options.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        {action === 'grant' && <label>Срок<select value={ttl} onChange={event => onTtl(Number(event.target.value))}>
          <option value={3600}>1 час</option><option value={86400}>1 день</option><option value={604800}>7 дней</option><option value={2592000}>30 дней</option></select></label>}
        <label>Номер заявки<input value={caseReference} onChange={event => onCaseReference(event.target.value)} minLength={3} maxLength={64} required /></label>
        <label>Текущий пароль<input type="password" value={password} onChange={event => onPassword(event.target.value)} autoComplete="current-password" required /></label>
        <button className="primary" disabled={!permission || !caseReference.trim() || !password}>{action === 'grant' ? 'Выдать право' : 'Отозвать право'}</button>
      </fieldset>
    </form>}
    {receipt && <div className="admin-receipt" role="status"><strong>Операция подтверждена сервером.</strong>
      <p>{receipt.action} · {receipt.permission} · {receipt.case_reference}</p></div>}
  </div>
}
