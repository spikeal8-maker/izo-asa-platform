import type { components } from './api.generated'
export type FoundationStatus = components['schemas']['FoundationStatus']
export type AuthView = components['schemas']['AuthView']
export type SessionList = components['schemas']['SessionList']

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code) }
}
type Options = {
  method?: 'GET' | 'POST' | 'DELETE'; data?: unknown; csrf?: string; signal?: AbortSignal
}
async function responseFor(path: string, options: Options): Promise<Response> {
  if (!path.startsWith('/api/v1/') || /[\\\r\n#]/.test(path)
      || new URL(path, window.location.origin).origin !== window.location.origin)
    throw new Error('Only the platform API is allowed')
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json'
    headers['X-IZO-Request'] = 'web'
    if (options.csrf) headers['X-CSRF-Token'] = options.csrf
  }
  const signal = options.signal
    ? AbortSignal.any([options.signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000)
  const response = await fetch(path, { method, headers, credentials: 'same-origin',
    cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer', signal,
    body: method === 'GET' ? undefined : JSON.stringify(options.data ?? {}) })
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('izo:session-invalid'))
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof body?.error?.code === 'string' ? body.error.code : 'api_unavailable')
  }
  return response
}
export async function apiRequest<T>(path: string, options: Options = {}): Promise<T> {
  const response = await responseFor(path, options)
  return response.status === 204 ? undefined as T : await response.json() as T
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
