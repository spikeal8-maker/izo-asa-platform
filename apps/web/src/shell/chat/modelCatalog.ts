import type { ChatPolicyView, CredentialView } from '../../shared/api'

export type ChatModel = ChatPolicyView['models'][number] & {
  text?: boolean
  vision?: boolean
  description?: string
  context_length?: number
  provider_brand?: string
  catalog_stale?: boolean
  catalog_dynamic?: boolean
}
export type ChatDisplayPolicy = Omit<ChatPolicyView, 'models'> & { models: ChatModel[] }

export const autoModel: ChatModel = { id: 'auto', label: 'Авто', provider: 'auto',
  text: true, vision: false, description: 'Автоматический выбор модели',
  price: { currency: 'RUB', input_kopeks_per_million: null,
    output_kopeks_per_million: null, image_kopeks_per_image: null } }
export const providerLabels: Record<string, string> = {
  deepseek: 'DeepSeek', openrouter: 'OpenRouter',
}
export function providerFor(model: ChatModel): string { return model.provider || 'deepseek' }

export function textModels(policy: ChatDisplayPolicy | null): ChatModel[] {
  return policy?.models ?? []
}

export function modelAvailable(model: ChatModel, credentials: CredentialView[]): boolean {
  return credentials.some(item => item.provider === providerFor(model) && item.verified)
}

export function groupedTextModels(models: ChatModel[]) {
  return ['deepseek', 'openrouter'].map(provider => ({
    provider, label: providerLabels[provider],
    models: models.filter(item => providerFor(item) === provider),
  })).filter(group => group.models.length > 0)
}

export function modelSearchText(model: ChatModel): string {
  const provider = providerFor(model)
  return `${model.label} ${model.id} ${providerLabels[provider] ?? provider} ${model.provider_brand ?? ''}`
    .toLocaleLowerCase('ru')
}

export function modelMeta(model: ChatModel): string {
  const provider = providerFor(model)
  const brand = model.provider_brand ?? providerLabels[provider] ?? provider
  const context = model.context_length && model.context_length > 0
    ? ` · контекст ${model.context_length.toLocaleString('ru-RU')}` : ''
  const stale = model.catalog_stale ? ' · сохранённый каталог' : ''
  return `${brand}${context}${stale}`
}
