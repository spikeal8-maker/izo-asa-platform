import { useCallback, useEffect, useRef, useState } from 'react'
import {
apiRequest, ApiError, chatProviderProblem,
type AuthView, type ChatPolicyView, type ChatRequestView, type CredentialListView, type CredentialView,
type ThreadView,
} from '../../shared/api'
import { useChatCatalog, useCredentialSync } from './useChatCatalog'
import { chatImageProblem, chatProblem, forgetChatOperations, resolveChatAttachments, type ChatAttachmentDraft } from './chatAttachments'
import { beginChatMedia, endChatMedia } from './AttachmentControl'
import { admitChatRequest, availableChatModel, PreflightProblem } from './useChatPreflight'
import { nextChatRequest, type PendingChatRequest } from './useConversationBranches'
import { useThreadSelection } from './useThreadSelection'
import { useThreadHistory } from './useThreadHistory'
import { streamChatRequest } from './streamChatRequest'
import { useAssistantAttempts } from './useAssistantAttempts'
import type { DisplayMessage } from './useConversationGraph'
export function useChatRuntime(auth: AuthView | null | undefined) {
const [basePolicy, setBasePolicy] = useState<ChatPolicyView | null>(null)
const [credentials, setCredentials] = useState<CredentialView[]>([])
const [messages, setMessages] = useState<DisplayMessage[]>([])
const [currentChatId, setCurrentChatId] = useState<string | null>(null)
const [busy, setBusy] = useState(false)
const [activeRequestId, setActiveRequestId] = useState<string | null>(null)
const [error, setError] = useState('')
const { history, historyCursor, loadingHistory, renamingThreadId, renameThread,
  resetHistory, loadMoreHistory, refreshHistory } = useThreadHistory(auth?.account.id, setError)
const idle = () => {setBusy(false);setActiveRequestId(null)}
const refreshPolicy = () => apiRequest<ChatPolicyView>('/api/v1/chat/policy').then(setBasePolicy)
const publishCredentialChange = useCredentialSync(auth, setCredentials)
const { policy, catalogError } = useChatCatalog(auth, basePolicy)
const streamController = useRef<AbortController | null>(null)
const pendingRequest = useRef<PendingChatRequest | null>(null)
const { selection, selectThread, selected, loadThread, loadOlder, olderCursor, loadingOlder, graph,
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
refreshHistory(controller.signal),
]).then(([p, c]) => {
if (controller.signal.aborted) return
setBasePolicy(p)
setCredentials(c.credentials)
}).catch(reason => {
if (!controller.signal.aborted) setError(chatProblem(reason))
})
return () => controller.abort()
}, [auth?.account.id])
useEffect(() => () => streamController.current?.abort(), [])
const streamRequest = useCallback(async (requestId: string, threadId: string) => {
await streamChatRequest(requestId, threadId, { selection, selected, streamController,
setBusy, setActiveRequestId, setMessages, setError, idle, loadThread, refreshHistory, isTerminal: graph.isTerminal })
}, [loadThread, refreshHistory, graph.isTerminal])
const attempts = useAssistantAttempts({ auth, threadId: currentChatId, busy,
pendingAdmission: Boolean(pendingRequest.current), graph, selection, selected, idle, stream: streamRequest,
reopen: () => currentChatId ? openThread(currentChatId, currentChatId) : Promise.resolve(false),
start: id => { setBusy(true); setActiveRequestId(id) } })
useEffect(() => {
if (!auth || busy || !currentChatId) return
const id = graph.value?.active_attempt?.request_id ?? [...messages].reverse().find(message =>
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
}, [auth?.account.id, busy, currentChatId, messages, openingThread, loadThread, streamRequest,
graph.value?.active_attempt?.request_id])
function newChat() {
if (attempts.navigationBlocked) return
resetSelection()
setCurrentChatId(null); setMessages([]); setError('')
}
const openChat = (chat: ThreadView) => attempts.navigationBlocked
  ? Promise.resolve(false) : openThread(chat.id, currentChatId)
async function send(text: string, selectedModelId: string, attachments: ChatAttachmentDraft[] = []): Promise<boolean> {
const selectedModel = availableChatModel(policy, credentials, selectedModelId)
if (!auth || !selectedModel || busy || attempts.pendingAdmission || attempts.saving
  || !pendingRequest.current && (graph.value && !graph.coherent.current || graph.value?.unknown_request_id)
  || !canSendTo(currentChatId, auth.account.id)) return false
setError(''); setBusy(true)
beginChatMedia(auth.account.id)
try {
let attachmentIds: string[]
try { attachmentIds = await resolveChatAttachments(attachments, auth, policy?.max_image_bytes ?? 0) }
catch (reason) { idle(); setError(chatImageProblem(reason)); return false }
let threadId = currentChatId
try {
if (!threadId) {
const thread = await apiRequest<ThreadView>('/api/v1/chat/threads', {
method: 'POST', csrf: auth.csrf_token, data: { title: null },
})
threadId = thread.id; setCurrentChatId(threadId)
selectThread(threadId)
await loadThread(threadId)
}
} catch (reason) {
idle(); setError(chatProblem(reason)); return false
}
const next = nextChatRequest(pendingRequest.current, threadId, text, selectedModel.id, attachmentIds,
  graph.current.current)
if (!next) {
idle(); setError('Проверьте предыдущий запрос.'); return false
}
const requestId = next.id
const replay = next === pendingRequest.current
pendingRequest.current = next
setActiveRequestId(requestId)
let accepted: ChatRequestView
try {
const result = await admitChatRequest(threadId, requestId, text, selectedModel,
  attachmentIds, auth.csrf_token, policy, replay, next.fence)
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
if (reason instanceof ApiError && reason.code === 'graph_revision_conflict') {
  graph.invalidate(); await attempts.branches.retry()
}
idle(); setError(chatProblem(reason)); return false
}
try { await loadThread(threadId); await refreshHistory() }
catch (reason) {
idle(); setError(chatProblem(reason)); return true
}
if (!graph.current.current || graph.current.current.active_attempt?.request_id === accepted.id)
  void streamRequest(accepted.id, threadId)
else idle()
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
policy, catalogError, credentials,
sidebar: { history, historyCursor, loadingHistory, renamingThreadId, currentChatId, busy,
onLoadMoreHistory: () => void loadMoreHistory(),
onRenameChat: (id: string, title: string) => auth ? renameThread(id, title, auth.csrf_token) : Promise.resolve(false) },
messages, openingThread, activeRequestId,
loadOlder: (beforePrepend: () => void) => currentChatId && loadOlder(currentChatId, beforePrepend),
olderCursor, loadingOlder,
pendingAdmission: Boolean(pendingRequest.current) || attempts.pendingAdmission,
attempts, branches: attempts.branches, executionBlocked: attempts.executionBlocked,
beforeGraphChange: graph.beforeChange,
error, setError, refreshPolicy, setCredential, credentialDisabled,
newChat, openChat, send, stop,
}
}
export type ChatRuntime = ReturnType<typeof useChatRuntime>
