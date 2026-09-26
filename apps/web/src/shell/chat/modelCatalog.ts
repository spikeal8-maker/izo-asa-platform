import type { ChatPolicyView, CredentialView } from '../../shared/api'
import type { IconName } from '../../shared/ui/Icon'

export type ChatModel = ChatPolicyView['models'][number] & {
  context_length?: number
  provider_brand?: string
  catalog_stale?: boolean
}
export type Tool = 'image' | 'video' | 'audio' | '3d' | 'web'

export const providerLabels: Record<string, string> = {
  deepseek: 'DeepSeek',
  openrouter: 'OpenRouter',
}

export const tools: { id: Tool; label: string; icon: IconName }[] = [
  { id: 'image', label: 'Создать изображение', icon: 'image' },
  { id: 'video', label: 'Создать видео', icon: 'video' },
  { id: 'audio', label: 'Создать звук', icon: 'audio' },
  { id: '3d', label: 'Создать 3D', icon: 'cube' },
  { id: 'web', label: 'Поиск в интернете', icon: 'globe' },
]

export const toolById = Object.fromEntries(
  tools.map(item => [item.id, item]),
) as Record<Tool, (typeof tools)[number]>

export function textModels(policy: ChatPolicyView | null): ChatModel[] {
  return policy?.models ?? []
}

export function selectedTextModel(
  policy: ChatPolicyView | null, selectedModelId: string | null,
): ChatModel | null {
  const models = textModels(policy)
  return models.find(item => item.id === selectedModelId)
    ?? models.find(item => item.id === policy?.default_model)
    ?? models[0]
    ?? null
}

export function providerCredential(
  credentials: CredentialView[], provider: string,
): CredentialView | null {
  return credentials.find(item => item.provider === provider) ?? null
}

export function modelAvailable(
  model: ChatModel, credentials: CredentialView[],
): boolean {
  return Boolean(providerCredential(credentials, model.provider)?.verified)
}

export function groupedTextModels(models: ChatModel[]) {
  const order = ['deepseek', 'openrouter']
  return order.map(provider => ({
    provider,
    label: providerLabels[provider] ?? provider,
    models: models.filter(item => item.provider === provider),
  })).filter(group => group.models.length > 0)
}

export function modelSearchText(model: ChatModel): string {
  return `${model.label} ${model.id} ${providerLabels[model.provider] ?? model.provider} ${model.provider_brand ?? ''}`
    .toLocaleLowerCase('ru')
}

export function modelMeta(model: ChatModel): string {
  const brand = model.provider_brand ?? providerLabels[model.provider] ?? model.provider
  const context = model.context_length && model.context_length > 0
    ? ` · контекст ${model.context_length.toLocaleString('ru-RU')}`
    : ''
  const stale = model.catalog_stale ? ' · сохранённый каталог' : ''
  return `${brand}${context}${stale}`
}
