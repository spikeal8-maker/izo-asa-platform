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
