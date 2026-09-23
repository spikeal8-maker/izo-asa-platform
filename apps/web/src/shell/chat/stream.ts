import { ApiError } from '../../shared/api'

export const chatErrors: Record<string, string> = {
  chat_preview_not_enabled: 'Этот аккаунт не допущен к локальному Chat preview.',
  credential_not_verified: 'Подключите и проверьте ключ DeepSeek.',
  credential_rejected: 'DeepSeek отклонил этот ключ.',
  credential_storage_unavailable: 'Хранилище ключей недоступно. Проверьте локальный root key.',
  credential_unavailable: 'Сохранённый ключ недоступен или был отключён.',
  credential_revision_conflict: 'Настройки ключа уже изменились. Обновите страницу.',
  credential_in_use: 'Сначала остановите активный ответ, затем замените ключ.',
  model_not_allowed: 'Выбранная модель не разрешена сервером.',
  active_request_exists: 'В этом чате уже выполняется ответ.',
  request_conflict: 'Повторный запрос имеет другие параметры.',
  chat_rate_limited: 'Достигнут временный лимит Chat. Повторите позднее.',
  provider_rate_limited: 'DeepSeek ограничил частоту запросов.',
  provider_balance: 'DeepSeek не разрешил запрос для этого ключа.',
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

export type StreamPayload = Record<string, unknown>

export async function consumeSse(
  response: Response, onEvent: (name: string, data: StreamPayload) => void,
) {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const part = await reader.read()
      if (part.done) break
      buffer += decoder.decode(part.value, { stream: true }).replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        let event = '', data = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (event && data) onEvent(event, JSON.parse(data) as StreamPayload)
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}
