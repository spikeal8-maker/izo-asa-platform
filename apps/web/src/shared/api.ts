import type { components } from './api.generated'
export type FoundationStatus = components['schemas']['FoundationStatus']
export type AuthView = components['schemas']['AuthView']
export type SessionList = components['schemas']['SessionList']

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code) }
}

export async function apiRequest<T>(path: string, options: {
  method?: 'GET' | 'POST' | 'DELETE'; data?: unknown; csrf?: string; signal?: AbortSignal
} = {}): Promise<T> {
  if (!path.startsWith('/api/v1/')) throw new Error('Only the platform API is allowed')
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json'
    headers['X-IZO-Request'] = 'web'
    if (options.csrf) headers['X-CSRF-Token'] = options.csrf
  }
  const response = await fetch(path, { method, headers, credentials: 'same-origin',
    signal: options.signal, body: method === 'GET' ? undefined : JSON.stringify(options.data ?? {}) })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof body?.error?.code === 'string' ? body.error.code : 'api_unavailable')
  }
  return response.status === 204 ? undefined as T : await response.json() as T
}

export async function getFoundation(signal: AbortSignal): Promise<FoundationStatus> {
  const data: unknown = await apiRequest('/api/v1/foundation', { signal })
  if (!data || typeof data !== 'object' || !('stage' in data) || data.stage !== 'foundation'
      || !('capabilities' in data) || !Array.isArray(data.capabilities)) {
    throw new Error('Unexpected API contract')
  }
  return data as FoundationStatus
}
