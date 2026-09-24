import type { components } from './api.generated'
export type FoundationStatus = components['schemas']['FoundationStatus']
export type AuthView = components['schemas']['AuthView']
export type GuestView = components['schemas']['GuestView']
export type SessionList = components['schemas']['SessionList']
export type ChatPolicyView = components['schemas']['ChatPolicyView']
export type CredentialView = components['schemas']['CredentialView']
export type ThreadView = components['schemas']['ThreadView']
export type ThreadList = components['schemas']['ThreadList']
export type MessageView = components['schemas']['MessageView']
export type ChatAttachmentView = components['schemas']['AttachmentView']
export type ThreadDetail = components['schemas']['ThreadDetail']
export type ChatRequestView = components['schemas']['RequestView']

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code) }
}
export const chatErrors: Record<string, string> = {
  chat_preview_not_enabled: 'Этот аккаунт не допущен к локальному Chat preview.',
  credential_not_verified: 'Подключите и проверьте ключ DeepSeek.',
  credential_rejected: 'DeepSeek отклонил этот ключ.',
  credential_storage_unavailable: 'Хранилище ключей недоступно. Проверьте локальный root key.',
  credential_unavailable: 'Сохранённый ключ недоступен или был отключён.',
  credential_revision_conflict: 'Настройки ключа уже изменились. Обновите страницу.',
  credential_in_use: 'Сначала остановите активный ответ, затем замените ключ.',
  model_not_allowed: 'Выбранная модель не разрешена сервером.',
  model_vision_unsupported: 'Модель не поддерживает изображения.',
  attachment_not_found: 'Вложение недоступно этому аккаунту.',
  attachment_unavailable: 'Изображение временно недоступно.',
  attachment_integrity_error: 'Не удалось безопасно прочитать сохранённое изображение.',
  image_too_large: 'Файл слишком большой для Chat.',
  active_request_exists: 'В этом чате уже выполняется ответ.',
  request_conflict: 'Повторный запрос имеет другие параметры.',
  chat_rate_limited: 'Достигнут временный лимит Chat. Повторите позднее.',
  provider_rate_limited: 'DeepSeek ограничил частоту запросов.',
  provider_balance: 'DeepSeek не разрешил запрос для этого ключа.',
  provider_empty_response: '????????? ???????? ?????? ??? ?????? ??????.',
  provider_output_limit: '????? ?????? ?????? ?????. ????????? ????? ????????.',
  provider_incomplete_response: '????????? ?? ?????????? ?????? ?????. ????????? ????? ????????.',
  provider_unavailable: 'DeepSeek сейчас недоступен.',
  provider_overloaded: 'DeepSeek перегружен. Автоматический повтор не выполнялся.',
  provider_stream_interrupted: 'Поток DeepSeek прервался. Частичный ответ сохранён.',
  request_expired: 'Время выполнения запроса истекло.',
  executor_restarted: 'Исполнитель был перезапущен. Частичный ответ сохранён.',
}
export function chatProblem(reason: unknown): string {
  if (reason instanceof ApiError) return chatErrors[reason.code]
    ?? (reason.status === 401 ? 'Войдите в аккаунт.' : 'Сервер отклонил Chat-запрос.')
  if (reason instanceof DOMException && reason.name === 'AbortError') return ''
  return 'Связь с Chat прервалась. Новый платный запрос автоматически не запускался.'
}
type Options = {
  method?: 'GET' | 'POST' | 'DELETE'
  data?: unknown
  binary?: ArrayBuffer
  contentType?: string
  csrf?: string
  signal?: AbortSignal
  timeoutMs?: number
}
async function responseFor(path: string, options: Options): Promise<Response> {
  if (!path.startsWith('/api/v1/') || /[\\\r\n#]/.test(path)
      || new URL(path, window.location.origin).origin !== window.location.origin)
    throw new Error('Only the platform API is allowed')
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (method !== 'GET') {
    headers['Content-Type'] = options.binary
      ? (options.contentType ?? 'application/octet-stream')
      : 'application/json'
    headers['X-IZO-Request'] = 'web'
    if (options.csrf) headers['X-CSRF-Token'] = options.csrf
  }
  const timeout = AbortSignal.timeout(options.timeoutMs ?? 15000)
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout
  const response = await fetch(path, { method, headers, credentials: 'same-origin',
    cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer', signal,
    body: method === 'GET' ? undefined
      : options.binary ?? JSON.stringify(options.data ?? {}) })
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('izo:session-invalid'))
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof body?.error?.code === 'string' ? body.error.code : 'api_unavailable')
  }
  return response
}
export async function apiRequest<T>(path: string, options: Options = {}): Promise<T> {
  try {
    const response = await responseFor(path, options)
    return response.status === 204 ? undefined as T : await response.json() as T
  } catch (reason) {
    if (path === '/api/v1/auth/me'
        && reason instanceof ApiError && reason.status === 401) {
      const response = await responseFor('/api/v1/auth/local-preview', {
        method: 'POST', data: {}, signal: options.signal,
      })
      const preview = await response.json() as T
      if (['/login', '/register'].includes(window.location.pathname)) {
        window.history.replaceState(null, '', '/')
        window.dispatchEvent(new Event('izo:navigate'))
      }
      return preview
    }
    throw reason
  }
}
export async function apiBinaryRequest<T>(
  path: string, binary: ArrayBuffer, csrf: string, signal?: AbortSignal,
): Promise<T> {
  const response = await responseFor(path, {
    method: 'POST', binary, contentType: 'application/octet-stream',
    csrf, signal, timeoutMs: 30000,
  })
  return await response.json() as T
}

export async function apiStream(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await responseFor(path, { signal, timeoutMs: 90000 })
  if (response.headers.get('content-type')?.split(';')[0] !== 'text/event-stream' || !response.body)
    throw new Error('Invalid event stream')
  return response
}

/** Read one authenticated PNG with a hard bound. Never prefetch a gallery's originals. */
export async function apiImage(path: string, byteSize: number, expectedHash: string, signal?: AbortSignal): Promise<Blob> {
  if (!Number.isSafeInteger(byteSize) || byteSize < 1 || byteSize > 65 * 1024 * 1024
      || !/^[a-f0-9]{64}$/.test(expectedHash)) throw new Error('Invalid image metadata')
  const response = await responseFor(path, { signal })
  if (response.headers.get('content-type')?.split(';')[0] !== 'image/png' || !response.body)
    throw new Error('Invalid image response')
  const reader = response.body.getReader()
  const chunks: Uint8Array<ArrayBuffer>[] = []
  let total = 0
  try {
    while (true) {
      const part = await reader.read()
      if (part.done) break
      total += part.value.byteLength
      if (total > byteSize) throw new Error('Image exceeds declared size')
      chunks.push(new Uint8Array(part.value))
    }
  } finally { await reader.cancel().catch(() => undefined); reader.releaseLock() }
  if (total !== byteSize) throw new Error('Incomplete image')
  const blob = new Blob(chunks, { type: 'image/png' })
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())))
    .map(value => value.toString(16).padStart(2, '0')).join('')
  if (hash !== expectedHash) throw new Error('Image checksum mismatch')
  return blob
}
export async function getFoundation(signal: AbortSignal): Promise<FoundationStatus> {
  const data: unknown = await apiRequest('/api/v1/foundation', { signal })
  if (!data || typeof data !== 'object' || !('stage' in data) || data.stage !== 'foundation'
      || !('capabilities' in data) || !Array.isArray(data.capabilities)) throw new Error('Unexpected API contract')
  return data as FoundationStatus
}
