export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code) }
}

export const chatErrors: Record<string, string> = {
  chat_preview_not_enabled: 'Этот аккаунт не допущен к локальному Chat preview.',
  credential_not_verified: 'Подключите и проверьте API key выбранного провайдера.',
  credential_rejected: 'Провайдер отклонил этот API key.',
  credential_storage_unavailable: 'Хранилище ключей недоступно. Проверьте локальный root key.',
  credential_unavailable: 'Сохранённый ключ недоступен или был отключён.',
  credential_revision_conflict: 'Настройки ключа уже изменились. Обновите страницу.',
  credential_in_use: 'Сначала остановите активный ответ, затем замените ключ.',
  credential_check_failed: 'Провайдер не подтвердил подключение. Повторите проверку.',
  provider_rejected: 'Провайдер отклонил проверку подключения.',
  model_not_allowed: 'Выбранная модель не разрешена сервером.',
  model_vision_unsupported: 'Модель не поддерживает изображения.',
  catalog_unavailable: 'Каталог OpenRouter временно недоступен.',
  attachment_not_found: 'Вложение недоступно этому аккаунту.',
  attachment_unavailable: 'Изображение временно недоступно.',
  attachment_integrity_error: 'Не удалось безопасно прочитать сохранённое изображение.',
  image_too_large: 'Файл слишком большой для Chat.',
  active_request_exists: 'В этом чате уже выполняется ответ.',
  request_conflict: 'Повторный запрос имеет другие параметры.',
  chat_rate_limited: 'Достигнут временный лимит Chat. Повторите позднее.',
  provider_rate_limited: 'Провайдер ограничил частоту запросов.',
  provider_balance: 'Провайдер не разрешил запрос для этого ключа.',
  provider_empty_response: 'Провайдер вернул пустой ответ.',
  provider_output_limit: 'Ответ достиг лимита длины. Попробуйте сузить запрос.',
  provider_incomplete_response: 'Провайдер не завершил ответ штатно. Попробуйте повторить.',
  provider_unavailable: 'Провайдер сейчас недоступен.',
  provider_overloaded: 'Провайдер перегружен. Автоматический повтор не выполнялся.',
  provider_stream_interrupted: 'Поток провайдера прервался. Частичный ответ сохранён.',
  request_expired: 'Время выполнения запроса истекло.',
  executor_restarted: 'Исполнитель был перезапущен. Частичный ответ сохранён.',
}

export function chatProviderProblem(code: string, provider?: string): string {
  const label = provider === 'openrouter'
    ? 'OpenRouter' : provider === 'deepseek' ? 'DeepSeek' : 'Провайдер'
  if (code === 'provider_unavailable') return `${label} сейчас недоступен.`
  if (code === 'provider_rate_limited') return `${label} ограничил частоту запросов.`
  if (code === 'provider_overloaded') return `${label} перегружен. Автоматический повтор не выполнялся.`
  if (code === 'provider_balance') return `${label} не разрешил запрос для этого ключа.`
  if (code === 'provider_stream_interrupted') return `Поток ${label} прервался. Частичный ответ сохранён.`
  return chatErrors[code] ?? 'Ответ завершился с ошибкой.'
}

export function chatProblem(reason: unknown): string {
  if (reason instanceof ApiError) return chatErrors[reason.code]
    ?? (reason.status === 401 ? 'Войдите в аккаунт.' : 'Сервер отклонил Chat-запрос.')
  if (reason instanceof DOMException && reason.name === 'AbortError') return ''
  return 'Связь с Chat прервалась. Новый платный запрос автоматически не запускался.'
}
