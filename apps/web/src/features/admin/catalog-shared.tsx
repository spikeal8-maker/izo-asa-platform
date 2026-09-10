import type { ReactNode } from 'react'
import type { components } from '../../shared/api.generated'
import { ApiError, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'

export type CapabilityView = components['schemas']['CapabilityView']
export type CapabilityList = components['schemas']['CapabilityList']
export type ConnectionView = components['schemas']['ConnectionView']
export type ConnectionList = components['schemas']['ConnectionList']
export type CredentialView = components['schemas']['CredentialView']
export type ProofView = components['schemas']['ProofView']
export type ChangeReceipt = components['schemas']['ChangeReceipt']
export type ProviderList = components['schemas']['ProviderList']

export const resolutions = ['512', '1K', '2K', '4K'] as const
export type Resolution = typeof resolutions[number]

export function has(auth: AuthView, permission: string) {
  return auth.account.permissions.includes(permission)
}

export function catalogError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) return 'Войдите в серверный аккаунт.'
    if (reason.code === 'verification_required') return 'Подтвердите почту административного аккаунта.'
    if (reason.code === 'revision_conflict' || reason.code === 'catalog_conflict') return 'Версия уже изменилась. Обновите данные перед повтором.'
    if (reason.code === 'idempotency_conflict') return 'Этот номер операции уже использован с другими параметрами. Обновите страницу.'
    if (reason.code === 'proof_prerequisite_missing') return 'Для проверки нужны черновик модели, подключение и действующая привязка секрета.'
    if (reason.code === 'contract_proof_failed') return 'Offline-проверка контракта не прошла. Проверьте модель, лимиты подключения и совпадение account/project/environment.'
    if (reason.code === 'proof_stale') return 'Проверка устарела после изменения модели, подключения или привязки секрета. Выполните её заново.'
    if (reason.code === 'credential_unavailable') return 'Действующая привязка секрета отсутствует.'
    if (reason.code === 'reauth_required') return 'Текущий пароль не подтверждён.'
    if (reason.status === 403) return 'Нет необходимого административного полномочия.'
    if (reason.status === 404) return 'Объект не найден или больше недоступен.'
    if (reason.status === 422) return 'Проверьте обязательные поля и допустимые значения.'
  }
  return 'Ответ сервера неизвестен. Повтор используйте с тем же номером операции; live-вызов не выполняется.'
}

export function CatalogNav({ auth }: { auth: AuthView }) {
  return <nav className="admin-links" aria-label="Административные страницы">
    {has(auth, 'users.read_limited') && <Link href="/admin/users">Пользователи</Link>}
    {has(auth, 'catalog.read') && <Link href="/admin/models">Модели</Link>}
    {has(auth, 'connections.read') && <Link href="/admin/providers">Провайдеры</Link>}
    {has(auth, 'connections.read') && has(auth, 'secrets.bind') && <Link href="/admin/credentials">Привязки секретов</Link>}
    {has(auth, 'audit.read') && <Link href="/admin/audit">Журнал действий</Link>}
    <Link href="/account/credits">Мои баллы</Link>
  </nav>
}

export function CatalogPanel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`admin-panel catalog-panel ${className}`.trim()}>{children}</section>
}

export function statusLabel(view: CapabilityView) {
  if (view.draft) return 'Черновик'
  if (view.published) return 'Опубликована metadata'
  return 'Выключена'
}

export function connectionStatus(view: ConnectionView) {
  if (view.draft) return 'Черновик'
  if (view.published) return 'Metadata опубликована · runtime выключен'
  return 'Не опубликовано · runtime выключен'
}
