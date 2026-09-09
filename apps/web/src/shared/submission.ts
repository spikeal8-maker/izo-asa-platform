import { isId } from './workspace-api'
import { ApiError } from './api'

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

/** Only replies documented as atomic pre-admission denials may clear a pending ID.
 * The status must match too: a familiar code inside a 500/unknown reply is NOT
 * proof that no job was committed. Auth/validation/throttle failures can happen
 * BEFORE replay lookup, so they cannot disprove an earlier successful submit.
 * Conflicts/replayed quotes remain pending.
 */
const deniedStatuses: Record<string, readonly number[]> = {
  quote_expired: [409], insufficient_credits: [409],
  plan_unconfigured: [403], plan_restricted: [409], image_size_restricted: [409],
  storage_quota_exceeded: [409], concurrency_limit: [409], rate_limited: [409],
  feature_unavailable: [409], jobs_disabled: [503],
  verification_required: [409], account_restricted: [409],
  input_limit: [409], invalid_input_usage: [409], action_budget_exceeded: [409],
  capability_unsupported: [409], provider_unavailable: [409],
}
export function rejectedBeforeAdmission(reason: unknown): boolean {
  return reason instanceof ApiError && Object.hasOwn(deniedStatuses, reason.code)
    && deniedStatuses[reason.code].includes(reason.status)
}
