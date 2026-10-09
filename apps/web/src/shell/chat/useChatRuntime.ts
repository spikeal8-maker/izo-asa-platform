import { useCallback, useEffect, useRef, useState } from 'react'
import {
apiRequest, ApiError, chatProviderProblem,
type AuthView, type ChatPolicyView, type ChatRequestView, type CredentialListView, type CredentialView,
type MessageView, type ThreadList, type ThreadView,
} from '../../shared/api'
import { useChatCatalog, useCredentialSync } from './useChatCatalog'
import { providerFor } from './modelCatalog'
import { chatImageProblem, chatProblem, forgetChatOperations, resolveChatAttachments, type ChatAttachmentDraft } from './chatAttachments'
import { beginChatMedia, endChatMedia } from './AttachmentControl'
import { admitChatRequest, nextChatRequest, PreflightProblem, type PendingChatRequest } from './useChatPreflight'
import { useThreadSelection } from './useThreadSelection'
import { useThreadHistory } from './useThreadHistory'
import { streamChatRequest } from './streamChatRequest'
export function useChatRuntime(auth: AuthView | null | undefined) {
const [basePolicy, setBasePolicy] = useState<ChatPolicyView | null>(null)
const [credentials, setCredentials] = useState<CredentialView[]>([])
const [messages, setMessages] = useState<MessageView[]>([])
const [currentChatId, setCurrentChatId] = useState<string | null>(null)
const [busy, setBusy] = useState(false)
const [activeRequestId, setActiveRequestId] = useState<string | null>(null)
const [error, setError] = useState('')
const { history, setHistory, historyCursor, setHistoryCursor, loadingHistory,
  resetHistory, loadMoreHistory, refreshHistory } = useThreadHistory(auth?.account.id, setError)
const idle = () => {setBusy(false);setActiveRequestId(null)}
const refreshPolicy = () => apiRequest<ChatPolicyView>('/api/v1/chat/policy').then(setBasePolicy)
const publishCredentialChange = useCredentialSync(auth, setCredentials)
const { policy, catalogError } = useChatCatalog(auth, basePolicy)
const streamController = useRef<AbortController | null>(null)
const pendingRequest = useRef<PendingChatRequest | null>(null)
const { selection, selectThread, selected, loadThread, loadOlder, olderCursor, loadingOlder,
openingThread, resetSelection, openThread, canSendTo, claimResume, clearResumeClaims, stopResume } = useThreadSelection(
auth?.account.id, { chatId: setCurrentChatId, messages: setMessages, error: setError })
useEffect(() => {
resetHistory()
streamController.current?.abort()
resetSelection()
setBasePolicy(null); setCredentials([]); setMessages([])
setCurrentChatId(null); idle(); setError('')
clearResumeClaims()
pendingRequest.current = null
if (!auth) return
const controller = new AbortController()
Promise.all([
apiRequest<ChatPolicyView>('/api/v1/chat/policy', { signal: controller.signal }),
apiRequest<CredentialListView>('/api/v1/chat/credentials', { signal: controller.signal }),
apiRequest<ThreadList>('/api/v1/chat/threads', { signal: controller.signal }),
]).then(([p, c, h]) => {
if (controller.signal.aborted) return
setBasePolicy(p)
setCredentials(c.credentials); setHistory(h.threads); setHistoryCursor(h.next_cursor ?? null)
}).catch(reason => {
if (!controller.signal.aborted) setError(chatProblem(reason))
})
return () => controller.abort()
}, [auth?.account.id])
useEffect(() => () => streamController.current?.abort(), [])
const streamRequest = useCallback(async (requestId: string, threadId: string) => {
await streamChatRequest(requestId, threadId, { selection, selected, streamController,
setBusy, setActiveRequestId, setMessages, setError, idle, loadThread, refreshHistory })
}, [loadThread, refreshHistory])
useEffect(() => {
if (!auth || busy || !currentChatId) return
const id = [...messages].reverse().find(message =>
message.role === 'assistant' && message.state === 'partial')?.request_id
if (!id) return
const claim = claimResume(currentChatId, id)
if (!claim) return
const controller = new AbortController()
const stale = () => controller.signal.aborted || !claim.current()
apiRequest<ChatRequestView>(`/api/v1/chat/requests/${id}`, { signal: controller.signal }).then(request => {
if (stale()) return
if (request.state === 'pending' || request.state === 'streaming')
void streamRequest(request.id, currentChatId)
else void loadThread(currentChatId)
}).catch(reason => { if (!stale()) setError(chatProblem(reason))
}).finally(() => { if (stale()) claim.release() })
return () => controller.abort()
}, [auth?.account.id, busy, currentChatId, messages, openingThread, loadThread, streamRequest])
function newChat() {
if (busy) return
resetSelection()
setCurrentChatId(null); setMessages([]); setError('')
}
const openChat = (chat: ThreadView) => busy ? Promise.resolve(false) : openThread(chat.id, currentChatId)
async function send(text: string, selectedModelId: string, attachments: ChatAttachmentDraft[] = []): Promise<boolean> {
const selectedModel = policy?.models.find(item => item.id === selectedModelId)
const selectedCredential = selectedModel
  ? credentials.find(item => item.provider === providerFor(selectedModel)) : null
if (!auth || !selectedModel || busy || !selectedCredential?.verified
  || !canSendTo(currentChatId, auth.account.id)) return false
setError(''); setBusy(true)
beginChatMedia(auth.account.id)
try {
let attachmentIds: string[]
try { attachmentIds = await resolveChatAttachments(attachments, auth, policy?.max_image_bytes ?? 0) }
catch (reason) { setBusy(false); setError(chatImageProblem(reason)); return false }
let threadId = currentChatId
try {
if (!threadId) {
const thread = await apiRequest<ThreadView>('/api/v1/chat/threads', {
method: 'POST', csrf: auth.csrf_token, data: { title: null },
})
threadId = thread.id; setCurrentChatId(threadId)
selectThread(threadId)
}
} catch (reason) {
setBusy(false); setError(chatProblem(reason)); return false
}
const next = nextChatRequest(pendingRequest.current, threadId, text, selectedModel.id, attachmentIds)
if (!next) {
setBusy(false); setError('Проверьте предыдущий запрос.'); return false
}
const requestId = next.id
const replay = next === pendingRequest.current
pendingRequest.current = next
setActiveRequestId(requestId)
let accepted: ChatRequestView
try {
const result = await admitChatRequest(threadId, requestId, text, selectedModel,
  attachmentIds, auth.csrf_token, policy, replay)
if (!result) {
idle()
setError('Приём неизвестен. Проверьте с тем же ID запроса.')
return false
}
accepted = result
pendingRequest.current = null
await forgetChatOperations(auth.account.id, attachments).catch(() => {})
} catch (reason) {
if (reason instanceof ApiError || reason instanceof PreflightProblem && !replay) pendingRequest.current = null
if (reason instanceof PreflightProblem) await refreshPolicy().catch(() => {})
idle(); setError(chatProblem(reason)); return false
}
try { await loadThread(threadId); await refreshHistory() }
catch (reason) {
idle(); setError(chatProblem(reason)); return true
}
void streamRequest(accepted.id, threadId)
return true
} finally { endChatMedia(auth.account.id) }
}
async function stop() {
if (!auth || !activeRequestId) return
const requestId = activeRequestId
try {
const stopped = await apiRequest<ChatRequestView>(
`/api/v1/chat/requests/${requestId}/stop`, {
method: 'POST', csrf: auth.csrf_token, data: {},
})
stopResume(requestId)
streamController.current?.abort()
const outcomeWarning = stopped.error_code === 'provider_outcome_unknown'
  ? chatProviderProblem(stopped.error_code) : ''
setError(outcomeWarning)
if (currentChatId) {
try { await loadThread(currentChatId) }
catch (reason) { if (!outcomeWarning) setError(chatProblem(reason)) }
}
} catch (reason) { setError(chatProblem(reason)) }
finally { idle() }
}
function setCredential(value: CredentialView) {
setCredentials(current => [...current.filter(item => item.provider !== value.provider), value])
publishCredentialChange()
}
function credentialDisabled(value: CredentialView) {
streamController.current?.abort()
setCredential(value); idle()
}
return {
policy, catalogError, credentials, history, historyCursor, loadingHistory, loadMoreHistory,
messages, currentChatId, openingThread, busy, activeRequestId,
loadOlder: (beforePrepend: () => void) => currentChatId && loadOlder(currentChatId, beforePrepend),
olderCursor, loadingOlder,
pendingAdmission: !!pendingRequest.current,
error, setError, refreshPolicy, setCredential, credentialDisabled,
newChat, openChat, send, stop,
}
}
export type ChatRuntime = ReturnType<typeof useChatRuntime>
