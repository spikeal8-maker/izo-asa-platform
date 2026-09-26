import { useEffect, useMemo, useState } from 'react'
import {
  ApiError, apiRequest, chatProblem,
  type AuthView, type ChatPolicyView, type OpenRouterCatalogView,
} from '../../shared/api'

export function useChatCatalog(
  auth: AuthView | null | undefined,
  policy: ChatPolicyView | null,
  onError: (message: string) => void,
): ChatPolicyView | null {
  const [catalog, setCatalog] = useState<OpenRouterCatalogView | null>(null)

  useEffect(() => {
    setCatalog(null)
    if (!auth) return
    const controller = new AbortController()
    apiRequest<OpenRouterCatalogView>(
      '/api/v1/chat/catalog/openrouter', { signal: controller.signal },
    ).then(value => {
      if (!controller.signal.aborted) setCatalog(value)
    }).catch(reason => {
      if (controller.signal.aborted) return
      onError(reason instanceof ApiError && reason.code === 'catalog_unavailable'
        ? 'Каталог OpenRouter временно недоступен.'
        : chatProblem(reason))
    })
    return () => controller.abort()
  }, [auth?.account.id])

  return useMemo(() => {
    if (!policy) return null
    const dynamic = (catalog?.models ?? []).map(item => ({
      id: item.id,
      label: item.name,
      provider: 'openrouter' as const,
      text: true,
      vision: false,
      description: 'Текстовая модель OpenRouter',
      context_length: item.context_length,
      provider_brand: item.provider,
      catalog_stale: catalog?.stale ?? false,
    }))
    return { ...policy, models: [...policy.models, ...dynamic] } as ChatPolicyView
  }, [policy, catalog])
}
