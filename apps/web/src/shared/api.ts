import type { components } from './api.generated'
export type FoundationStatus = components['schemas']['FoundationStatus']

export async function getFoundation(signal: AbortSignal): Promise<FoundationStatus> {
  const response = await fetch('/api/v1/foundation', { signal, credentials: 'same-origin' })
  if (!response.ok) throw new Error('API unavailable')
  const data: unknown = await response.json()
  if (!data || typeof data !== 'object' || !('stage' in data) || data.stage !== 'foundation'
      || !('capabilities' in data) || !Array.isArray(data.capabilities)) {
    throw new Error('Unexpected API contract')
  }
  return data as FoundationStatus
}
