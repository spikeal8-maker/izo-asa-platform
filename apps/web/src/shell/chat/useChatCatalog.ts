import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react'
import {
  apiRequest, type AuthView, type ChatPolicyView, type CredentialListView, type CredentialView, type OpenRouterCatalogView,
} from '../../shared/api'
import type { ChatDisplayPolicy, ChatModel } from './modelCatalog'

export function fetchOpenRouterCatalog(signal?: AbortSignal) {
  return apiRequest<OpenRouterCatalogView>('/api/v1/chat/catalog/openrouter', { signal })
}

export function useChatCatalog(
  auth: AuthView | null | undefined,
  policy: ChatPolicyView | null,
): { policy: ChatDisplayPolicy | null; catalogError: string } {
  const [catalog, setCatalog] = useState<OpenRouterCatalogView | null>(null)
  const [catalogError, setCatalogError] = useState('')

  useEffect(() => {
    setCatalog(null); setCatalogError('')
    if (!auth) return
    const controller = new AbortController()
    fetchOpenRouterCatalog(controller.signal).then(value => {
      if (!controller.signal.aborted) setCatalog(value)
    }).catch(() => {
      if (!controller.signal.aborted) setCatalogError('Каталог OpenRouter временно недоступен.')
    })
    return () => controller.abort()
  }, [auth?.account.id])

  const displayPolicy = useMemo<ChatDisplayPolicy | null>(() => {
    if (!policy) return null
    const known = new Set(policy.models.map(item => item.id))
    const dynamic: ChatModel[] = (catalog?.models ?? [])
      .filter(item => !known.has(item.id))
      .map(item => ({
        id: item.id,
        label: item.name,
        provider: 'openrouter',
        price: { currency: 'RUB', input_kopeks_per_million: null,
          output_kopeks_per_million: null, image_kopeks_per_image: null },
        text: true,
        vision: item.vision,
        description: item.vision
          ? 'Модель поддерживает изображения; отправка в чате пока недоступна'
          : 'Текстовая модель OpenRouter',
        context_length: item.context_length,
        provider_brand: item.provider,
        catalog_stale: catalog?.stale ?? false,
        catalog_dynamic: true,
      }))
    return { ...policy, models: [...policy.models, ...dynamic] }
  }, [policy, catalog])

  return { policy: displayPolicy, catalogError }
}

const keyFor = (accountId: string) => `izo-chat-credentials-updated:${accountId}`

export function useCredentialSync(
  auth: AuthView | null | undefined,
  setCredentials: Dispatch<SetStateAction<CredentialView[]>>,
) {
  const accountId = auth?.account.id

  useEffect(() => {
    if (!accountId) return
    let active = true
    let serial = 0
    const refresh = () => {
      if (document.visibilityState === 'hidden') return
      const currentRequest = ++serial
      void apiRequest<CredentialListView>('/api/v1/chat/credentials')
        .then(value => {
          if (!active || currentRequest !== serial) return
          setCredentials(current => value.credentials.map(item => {
            const latest = current.find(saved => saved.provider === item.provider)
            return latest && (latest.revision ?? 0) > (item.revision ?? 0)
              ? latest : item
          }))
        })
        .catch(() => { /* Keep the last known status until the next refresh. */ })
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key === keyFor(accountId)) refresh()
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', onStorage)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      active = false
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', onStorage)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [accountId, setCredentials])

  return useCallback(() => {
    if (!accountId) return
    try { localStorage.setItem(keyFor(accountId), crypto.randomUUID()) }
    catch { /* The current tab already has the updated credential view. */ }
  }, [accountId])
}

type StreamPayload = Record<string, unknown>
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
  } finally { reader.releaseLock() }
}
