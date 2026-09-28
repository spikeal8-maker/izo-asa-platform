import { useCallback, useEffect, useRef, useState } from 'react'
import {
apiRequest, apiStream, ApiError, chatProviderProblem,
type AuthView, type ChatPolicyView, type ChatRequestView, type CredentialListView, type CredentialView,
type MessageView, type ThreadDetail, type ThreadList, type ThreadView,
} from '../../shared/api'
import { consumeSse, useChatCatalog, useCredentialSync } from './useChatCatalog'
import { providerFor } from './modelCatalog'
import { chatImageProblem, chatProblem, forgetChatOperations, lastChatWarning, resolveChatAttachments, type ChatAttachmentDraft } from './chatAttachments'
import { beginChatMedia, endChatMedia } from './AttachmentControl'
import { admitChatRequest, nextChatRequest, PreflightProblem, type PendingChatRequest } from './useChatPreflight'
export function useChatRuntime(auth: AuthView | null | undefined) {
const [basePolicy, setBasePolicy] = useState<ChatPolicyView | null>(null)
const [credentials, setCredentials] = useState<CredentialView[]>([])
const [history, setHistory] = useState<ThreadView[]>([])
const [messages, setMessages] = useState<MessageView[]>([])
const [currentChatId, setCurrentChatId] = useState<string | null>(null)
const [busy, setBusy] = useState(false)
const [activeRequestId, setActiveRequestId] = useState<string | null>(null)
const [error, setError] = useState('')
const idle = () => {setBusy(false);setActiveRequestId(null)}
const refreshPolicy = () => apiRequest<ChatPolicyView>('/api/v1/chat/policy').then(setBasePolicy)
const publishCredentialChange = useCredentialSync(auth, setCredentials)
const { policy, catalogError } = useChatCatalog(auth, basePolicy)
const streamController = useRef<AbortController | null>(null)
const resumeAttempted = useRef(new Set<string>())
const pendingRequest = useRef<PendingChatRequest | null>(null)
const refreshHistory = useCallback(async (signal?: AbortSignal) => {
if (!auth) return
const list = await apiRequest<ThreadList>('/api/v1/chat/threads', { signal })
setHistory(list.threads)
}, [auth?.account.id])
const loadThread = useCallback(async (threadId: string, signal?: AbortSignal) => {
const detail = await apiRequest<ThreadDetail>(
`/api/v1/chat/threads/${threadId}`, { signal })
setCurrentChatId(detail.thread.id); setMessages(detail.messages)
const warning = await lastChatWarning(detail.messages, signal)
if (warning) setError(warning)
return detail
}, [])
useEffect(() => {
streamController.current?.abort()
setBasePolicy(null); setCredentials([]); setHistory([]); setMessages([])
setCurrentChatId(null); idle(); setError('')
resumeAttempted.current.clear()
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
setCredentials(c.credentials); setHistory(h.threads)
}).catch(reason => {
if (!controller.signal.aborted) setError(chatProblem(reason))
})
return () => controller.abort()
}, [auth?.account.id])
useEffect(() => () => streamController.current?.abort(), [])
const streamRequest = useCallback(async (requestId: string, threadId: string) => {
const controller = new AbortController()
streamController.current?.abort(); streamController.current = controller
setBusy(true); setActiveRequestId(requestId)
setMessages(current => current.map(message =>
message.request_id === requestId && message.role === 'assistant'
? { ...message, content: '', state: 'partial' } : message))
try {
const response = await apiStream(
`/api/v1/chat/requests/${requestId}/events`, controller.signal)
await consumeSse(response, (name, data) => {
if (name === 'text.delta' && typeof data.text === 'string') {
setMessages(current => current.map(message =>
message.request_id === requestId && message.role === 'assistant'
? { ...message, content: message.content + data.text, state: 'partial' }
: message))
} else if (name === 'message.error' && typeof data.code === 'string') {
setError(chatProviderProblem(data.code,
  typeof data.provider === 'string' ? data.provider : undefined))
} else if (name === 'message.interrupted') {
setError(data.code === 'provider_outcome_unknown' || data.reason === 'provider_outcome_unknown'
  ? chatProviderProblem('provider_outcome_unknown')
  : data.reason === 'stopped' ? ''
  : 'Ответ был прерван. Частичный текст сохранён.')
}
})
} catch (reason) {
if (!controller.signal.aborted) setError(chatProblem(reason))
} finally {
if (streamController.current === controller) streamController.current = null
idle()
try { await loadThread(threadId); await refreshHistory() }
catch (reason) { setError(current => current || chatProblem(reason)) }
}
}, [loadThread, refreshHistory])
useEffect(() => {
if (!auth || busy || !currentChatId) return
const assistant = [...messages].reverse().find(
message => message.role === 'assistant' && message.state === 'partial')
if (!assistant || resumeAttempted.current.has(assistant.request_id)) return
resumeAttempted.current.add(assistant.request_id)
const controller = new AbortController()
apiRequest<ChatRequestView>(
`/api/v1/chat/requests/${assistant.request_id}`,
{ signal: controller.signal },
).then(request => {
if (controller.signal.aborted) return
if (request.state === 'pending' || request.state === 'streaming')
void streamRequest(request.id, currentChatId)
else void loadThread(currentChatId)
}).catch(reason => {
if (!controller.signal.aborted) setError(chatProblem(reason))
})
return () => controller.abort()
}, [auth?.account.id, busy, currentChatId, messages, loadThread, streamRequest])
function newChat() {
if (busy) return
setCurrentChatId(null); setMessages([]); setError('')
}
async function openChat(chat: ThreadView) {
if (busy) return
setError('')
try { await loadThread(chat.id) }
catch (reason) { setError(chatProblem(reason)) }
}
async function send(text: string, selectedModelId: string, attachments: ChatAttachmentDraft[] = []): Promise<boolean> {
const selectedModel = policy?.models.find(item => item.id === selectedModelId)
const selectedCredential = selectedModel
  ? credentials.find(item => item.provider === providerFor(selectedModel)) : null
if (!auth || !selectedModel || busy || !selectedCredential?.verified) return false
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
resumeAttempted.current.add(requestId)
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
policy, catalogError, credentials, history, messages, currentChatId, busy, activeRequestId,
pendingAdmission: !!pendingRequest.current,
error, setError, refreshPolicy, setCredential, credentialDisabled,
newChat, openChat, send, stop,
}
}
export type ChatRuntime = ReturnType<typeof useChatRuntime>
