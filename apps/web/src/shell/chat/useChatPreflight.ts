import { apiRequest, ApiError, chatProviderProblem, type ChatPolicyView, type ChatRequestView } from '../../shared/api'
import type { ChatDisplayPolicy, ChatModel } from './modelCatalog'
import { fetchOpenRouterCatalog } from './useChatCatalog'
import { isId } from '../../shared/workspace-api'
import type { ChatAttachmentDraft, ImageType, Prepared } from './chatAttachments'

export class ImageProblem extends Error {
  constructor(public code: 'type' | 'size' | 'decode' | 'uncertain' | 'storage' | 'terminal' | 'other_tab' | 'locks') { super(code) }
}
export class PreflightProblem extends Error {}
type Pending = { operationId: string; hash: string; type: ImageType; size: number;
  width: number; height: number; started: boolean }
const keyFor = (accountId: string) => `izo-chat-pending-media:${accountId}`
function pending(accountId: string): Pending[] {
  if (!isId(accountId)) throw new ImageProblem('storage')
  try {
    const raw = localStorage.getItem(keyFor(accountId))
    if (raw === null) return []
    const value: unknown = JSON.parse(raw)
    if (!Array.isArray(value) || value.some(item => !item || !isId(item.operationId)
      || !/^[0-9a-f]{64}$/.test(item.hash)
      || !['image/png', 'image/jpeg', 'image/webp'].includes(item.type)
      || !Number.isSafeInteger(item.size) || item.size < 1
      || !Number.isSafeInteger(item.width) || !Number.isSafeInteger(item.height)
      || typeof item.started !== 'boolean')) throw new Error('Invalid pending Media metadata')
    return value as Pending[]
  } catch { throw new ImageProblem('storage') }
}
function save(accountId: string, items: Pending[]) {
  try { localStorage.setItem(keyFor(accountId), JSON.stringify(items)) }
  catch { throw new ImageProblem('storage') }
}
function withLock<T>(accountId: string, action: () => T): Promise<T> {
  return navigator.locks ? navigator.locks.request(`izo-chat-media:${accountId}`, action)
    : Promise.resolve().then(action)
}
const leases = new Map<string, { ready: Promise<boolean>; release: () => void }>()
async function ownChatMedia(accountId: string) {
  if (!navigator.locks) throw new ImageProblem('locks')
  let lease = leases.get(accountId)
  if (!lease) {
    let release = () => {}
    const ready = new Promise<boolean>(resolve => {
      void navigator.locks.request(`izo-chat-media-tab:${accountId}`, { ifAvailable: true }, lock => {
        resolve(Boolean(lock))
        return lock ? new Promise<void>(done => { release = done }) : undefined
      }).catch(() => resolve(false))
    })
    lease = { ready, release: () => release() }
    leases.set(accountId, lease)
  }
  if (!await lease.ready) { leases.delete(accountId); throw new ImageProblem('other_tab') }
}
function releaseIfEmpty(accountId: string, items: Pending[]) {
  if (items.length) return
  releaseChatMedia(accountId)
}
export function releaseChatMedia(accountId: string) {
  leases.get(accountId)?.release()
  leases.delete(accountId)
}
export function pendingChatNotice(accountId?: string): string {
  if (!accountId) return ''
  try { return pending(accountId).some(item => item.started)
    ? 'Есть незавершённая загрузка. Выберите тот же файл для проверки состояния.' : '' }
  catch { return 'Не удалось прочитать состояние загрузки. Новая загрузка заблокирована.' }
}
export function reserveChatOperation(accountId: string, image: Prepared, used: Set<string>) {
  return ownChatMedia(accountId).then(() => withLock(accountId, () => {
    const items = pending(accountId)
    const old = items.find(item => !used.has(item.operationId) && item.hash === image.hash
      && item.type === image.type && item.size === image.bytes.byteLength
      && item.width === image.width && item.height === image.height)
    if (old) return old.operationId
    const operationId = crypto.randomUUID()
    save(accountId, [...items, { operationId, hash: image.hash, type: image.type,
      size: image.bytes.byteLength, width: image.width, height: image.height, started: false }])
    return operationId
  }))
}
export function markChatOperationStarted(accountId: string, operationId: string, image: Prepared) {
  return withLock(accountId, () => {
    const items = pending(accountId)
    const item = items.find(entry => entry.operationId === operationId)
    if (!item || item.hash !== image.hash || item.type !== image.type
      || item.size !== image.bytes.byteLength || item.width !== image.width
      || item.height !== image.height) throw new ImageProblem('storage')
    item.started = true
    save(accountId, items)
  })
}
export function forgetChatOperations(accountId: string | undefined, drafts: ChatAttachmentDraft[]) {
  if (!accountId || !drafts.length) return Promise.resolve()
  const used = new Set(drafts.map(item => item.operationId))
  return withLock(accountId, () => { const items = pending(accountId).filter(item => !used.has(item.operationId))
    save(accountId, items); releaseIfEmpty(accountId, items) })
}
export function forgetUnstartedOperations(accountId: string | undefined, drafts: Pick<ChatAttachmentDraft, 'operationId'>[]) {
  if (!accountId || !drafts.length) return Promise.resolve()
  const used = new Set(drafts.map(item => item.operationId))
  return withLock(accountId, () => { const items = pending(accountId).filter(item =>
    item.started || !used.has(item.operationId))
    save(accountId, items); releaseIfEmpty(accountId, items) })
}

export type PendingChatRequest = { id: string; threadId: string; payload: string }
export function nextChatRequest(previous: PendingChatRequest | null, threadId: string,
  text: string, model: string, attachmentIds: string[]): PendingChatRequest | null {
  const payload = JSON.stringify([text, model, attachmentIds])
  if (previous && (previous.threadId !== threadId || previous.payload !== payload)) return null
  return previous ?? { id: crypto.randomUUID(), threadId, payload }
}

/** Recheck server-owned price and model capabilities immediately before admission. */
export async function chatPreflight(policy: ChatDisplayPolicy | null, model: ChatModel,
  images: number, signal: AbortSignal): Promise<string> {
  let latest: ChatPolicyView
  try { latest = await apiRequest<ChatPolicyView>('/api/v1/chat/policy', { signal, timeoutMs: 6000 }) }
  catch { return signal.aborted ? '' : 'Не удалось проверить цену и модель. Повторите позже.' }
  if (signal.aborted) return ''
  if (latest.revision !== policy?.revision)
    return 'Модели или цены изменились — обновите чат перед отправкой.'
  if (images && (images > latest.max_attachments || !latest.max_image_bytes))
    return 'Лимиты изображений изменились — обновите чат перед отправкой.'
  if (model.catalog_dynamic) {
    try {
      const current = await fetchOpenRouterCatalog(signal)
      const found = current.models.find(item => item.id === model.id)
      if (current.stale || !found) return 'Каталог OpenRouter изменился — обновите список моделей.'
      if (images && !found.vision) return 'Выбранная модель больше не принимает изображения.'
    } catch { return signal.aborted ? '' : 'Не удалось проверить каталог OpenRouter. Повторите позже.' }
  } else {
    const found = latest.models.find(item => item.id === model.id)
    if (!found) return 'Выбранная модель больше недоступна. Выберите другую модель.'
    if (images && !found.vision) return 'Выбранная модель не принимает изображения.'
  }
  return ''
}

/** Exact request-ID replay is the only safe path after uncertain Chat admission. */
export async function admitChatRequest(threadId: string, requestId: string, text: string,
  model: ChatModel, attachmentIds: string[], csrf: string, policy: ChatDisplayPolicy | null,
  replay: boolean): Promise<ChatRequestView | null> {
  if (replay) {
    try { return await apiRequest<ChatRequestView>(`/api/v1/chat/requests/${requestId}`, { timeoutMs: 10000 }) }
    catch (reason) { if (!(reason instanceof ApiError && reason.status === 404)) return null }
  }
  if (attachmentIds.length) {
    const problem = await chatPreflight(policy, model, attachmentIds.length, new AbortController().signal)
    if (problem) throw new PreflightProblem(problem)
  }
  try {
    return await apiRequest<ChatRequestView>(`/api/v1/chat/threads/${threadId}/requests`, {
      method: 'POST', csrf, data: { request_id: requestId, text, model: model.id, attachment_ids: attachmentIds },
      timeoutMs: 20000,
    })
  } catch (reason) {
    if (reason instanceof ApiError) throw reason
    try { return await apiRequest<ChatRequestView>(`/api/v1/chat/requests/${requestId}`, { timeoutMs: 10000 }) }
    catch { return null }
  }
}

export async function persistedChatWarning(requestId: string, signal?: AbortSignal): Promise<string> {
  try {
    const request = await apiRequest<ChatRequestView>(`/api/v1/chat/requests/${requestId}`, { signal })
    return request.error_code === 'provider_outcome_unknown' ? chatProviderProblem(request.error_code) : ''
  } catch { return '' }
}
