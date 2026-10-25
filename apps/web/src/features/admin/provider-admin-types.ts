import { ApiError } from '../../shared/api'

export type Provider = {
  provider: 'deepseek'
  configured: boolean
  enabled: boolean
  verified: boolean
  status: 'not_configured' | 'not_verified' | 'disabled' | 'verified'
  model: 'deepseek-flash' | 'deepseek-v4-pro'
  revision: number | null
  generation: number | null
  daily_limit: number
  concurrency_limit: number
  available_to_users: boolean
}
export type ProviderList = { connections: Provider[] }
export const endpoint = '/api/v1/admin/providers'
export const labels: Record<Provider['status'], string> = {
  not_configured: 'Ключ не настроен',
  not_verified: 'Требуется проверка ключа',
  disabled: 'Выключено',
  verified: 'Ключ проверен, настройка включена',
}

export function explainProviderError(reason: unknown): string {
  if (reason instanceof ApiError) {
    const errors: Record<string, string> = {
      forbidden: 'Недостаточно полномочий для операции.',
      verification_required: 'Подтвердите административную учётную запись.',
      reauth_required: 'Неверный текущий пароль администратора.',
      provider_not_verified: 'Сначала проверьте подключение.',
      provider_not_configured: 'Сначала сохраните ключ.',
      provider_revision_conflict: 'Настройки изменились. Обновите данные.',
      provider_changed_during_verify: 'Ключ изменился во время проверки. Повторите чтение.',
      credential_rejected: 'Проверка отклонила ключ. Подключение не подтверждено.',
      credential_unavailable: 'Не удалось прочитать зашифрованный ключ.',
      credential_storage_unavailable: 'На сервере недоступен корневой ключ шифрования.',
      rate_limited: 'Достигнут лимит проверок. Повторите позже.',
      invalid_input: 'Проверьте поля и ограничения.'
    }
    return errors[reason.code] ?? 'Сервер отклонил операцию (' + reason.code + ').'
  }
  return 'Нет ответа от сервера. Обновите данные перед повтором.'
}
