import type { ChatPolicyView } from '../../shared/api'
import type { ChatModel } from './types'

export function configuredModels(policy: ChatPolicyView | null): ChatModel[] {
  return policy?.models ?? []
}

export function selectedModel(
  policy: ChatPolicyView | null, currentId: string | null,
): ChatModel | null {
  const models = configuredModels(policy)
  return models.find(item => item.id === currentId)
    ?? models.find(item => item.id === policy?.default_model)
    ?? models[0]
    ?? null
}
