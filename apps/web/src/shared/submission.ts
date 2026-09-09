import { isId } from './workspace-api'

export type Pending = { version: 1; owner: string; quote_id: string; operation_id: string }
export const submissionKey = (owner: string) => `izo-pending-submit:${owner}`

/** Only idempotency IDs, never prompt, cookies, CSRF, keys, balance or image bytes. */
export function readPending(owner: string): Pending | null {
  const raw = sessionStorage.getItem(submissionKey(owner))
  if (!raw) return null
  if (raw.length > 500) throw new Error('Damaged pending command')
  const value = JSON.parse(raw) as Pending
  if (value.version !== 1 || value.owner !== owner || !isId(owner)
      || !isId(value.quote_id) || !isId(value.operation_id)
      || Object.keys(value).sort().join(',') !== 'operation_id,owner,quote_id,version')
    throw new Error('Damaged pending command')
  return value
}
export function remember(owner: string, quoteId: string): Pending {
  if (!isId(owner) || !isId(quoteId)) throw new Error('Invalid pending command')
  const previous = readPending(owner)
  if (previous) return previous
  const value: Pending = { version: 1, owner, quote_id: quoteId, operation_id: crypto.randomUUID() }
  sessionStorage.setItem(submissionKey(owner), JSON.stringify(value))
  const saved = readPending(owner)
  if (!saved || saved.operation_id !== value.operation_id) throw new Error('Cannot persist request identity')
  return saved
}
export function forget(owner: string) { sessionStorage.removeItem(submissionKey(owner)) }
