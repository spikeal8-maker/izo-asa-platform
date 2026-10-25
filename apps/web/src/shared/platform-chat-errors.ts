/** Synthetic platform route errors use existing Chat UI semantics. */
export const platformChatErrors: Record<string, string> = {
  platform_daily_limit: 'Дневной лимит платформенного ИИ исчерпан. Используйте свой ключ или повторите завтра.',
  platform_concurrency_limit: 'Платформенная модель занята. Дождитесь завершения другого ответа.',
  platform_model_unavailable: 'Платформенная модель выключена или её настройки изменились. Обновите список моделей.',
}
