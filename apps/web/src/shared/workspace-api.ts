import type { components } from './api.generated'
import { apiImage, apiRequest, ApiError, type AuthView } from './api'

export type Job = components['schemas']['JobView']
export type Jobs = components['schemas']['JobList']
export type Quote = components['schemas']['QuoteView']
export type Asset = components['schemas']['AssetView']
export type Assets = components['schemas']['AssetList']
export type Plan = components['schemas']['EntitlementView']
export type Credits = components['schemas']['Overview']
export type Draft = components['schemas']['QuoteInput']
export const isId = (value: string) => /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value)
export const activeJob = (job: Job) => !['succeeded', 'failed', 'cancelled'].includes(job.status)
export const statusName: Record<Job['status'], string> = {
  queued: 'В очереди', claimed: 'Принято исполнителем', running: 'Выполняется',
  uploading: 'Сохраняем файл', reconciling: 'Уточняем результат', succeeded: 'Готово', failed: 'Ошибка', cancelled: 'Отменено',
}
const explanations: Record<string, string> = {
  auth_required: 'Войдите в аккаунт.', verification_required: 'Подтвердите почту в настройках аккаунта.',
  account_restricted: 'Для аккаунта ограничены новые операции. Обратитесь к оператору.',
  plan_unconfigured: 'Оператор ещё не назначил доступные модели и лимиты.',
  plan_restricted: 'Тестовый исполнитель не входит в ваш план.', feature_unavailable: 'Задания на этом стенде выключены.',
  jobs_disabled: 'Задания на этом стенде выключены.', image_size_restricted: 'Этот размер не разрешён вашим планом.',
  provider_unavailable: 'Исполнитель сейчас недоступен. Сервер не принял новое задание; повторите расчёт позднее.',
  capability_unsupported: 'Этот режим не поддерживается исполнителем. Выберите доступную модель.',
  action_budget_exceeded: 'Стоимость превышает лимит одной операции в вашем плане. Задание не принято.',
  input_limit: 'Исходники превышают ограничения вашего плана.',
  invalid_input_usage: 'Сервер не подтвердил параметры исходников. Проверьте их перед новой оценкой.',
  insufficient_credits: 'Недостаточно баллов. Сохранённые работы остаются доступны.',
  concurrency_limit: 'Достигнут предел активных заданий. Откройте список заданий.',
  storage_quota_exceeded: 'Недостаточно свободного места с учётом текущих резервов.',
  rate_limited: 'Достигнут лимит запросов. Повторите позднее.', quote_rate_limited: 'Слишком много запросов цены.',
  quote_expired: 'Цена устарела. Получите новую оценку перед подтверждением.',
  quote_already_used: 'Эта оценка уже использована. Проверьте список заданий.',
  idempotency_conflict: 'Параметры повторного запроса отличаются. Проверьте список заданий.',
  not_found: 'Объект не найден или недоступен этому аккаунту.',
  csrf_rejected: 'Сессия изменилась. Обновите страницу.',
  reconciliation_required: 'Автоматическая проверка исчерпана. Нужен разбор оператором; резерв пока сохранён.',
  storage_uncertain: 'Сервер уточняет запись файла. Не запускайте повторную генерацию.',
}
export function problem(reason: unknown): string {
  if (reason instanceof ApiError) return explanations[reason.code]
    ?? (reason.status === 401 ? 'Войдите в аккаунт.' : reason.status === 404
      ? explanations.not_found : 'Сервер отклонил запрос. Обновите данные или обратитесь к оператору.')
  return 'Не удалось получить ответ сервера. Проверьте соединение и повторите проверку.'
}
export function navigate(path: string) {
  window.history.pushState(null, '', path)
  window.dispatchEvent(new Event('izo:navigate'))
  window.scrollTo({ top: 0 })
}
export async function downloadTicket(asset: Asset, auth: AuthView, signal?: AbortSignal): Promise<string> {
  if (!isId(asset.id)) throw new Error('Invalid asset')
  const ticket = await apiRequest<components['schemas']['DownloadView']>(`/api/v1/media/assets/${asset.id}/download`,
    { method: 'POST', csrf: auth.csrf_token, signal })
  const expected = `/api/v1/media/assets/${asset.id}/content?ticket=`
  if (!ticket.url.startsWith(expected) || !/^[A-Za-z0-9_-]{43}$/.test(ticket.url.slice(expected.length))
      || ticket.expires_at * 1000 <= Date.now()) throw new Error('Invalid download ticket')
  return ticket.url
}
export async function imageBlob(asset: Asset, auth: AuthView, signal?: AbortSignal): Promise<Blob> {
  const url = await downloadTicket(asset, auth, signal)
  return apiImage(url, asset.byte_size, asset.sha256, signal)
}
