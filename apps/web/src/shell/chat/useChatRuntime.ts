import { useCallback, useEffect, useRef, useState } from 'react'
import {
apiRequest, apiStream, ApiError, chatErrors, chatProblem,
type AuthView, type ChatPolicyView, type ChatRequestView, type CredentialView,
type MessageView, type ThreadDetail, type ThreadList, type ThreadView,
} from '../../shared/api'
type ChatModel = ChatPolicyView['models'][number]
type StreamPayload = Record<string, unknown>
async function consumeSse(
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
export function useChatRuntime(auth: AuthView | null | undefined) {
const [policy, setPolicy] = useState<ChatPolicyView | null>(null)
const [credential, setCredential] = useState<CredentialView | null>(null)
const [history, setHistory] = useState<ThreadView[]>([])
const [messages, setMessages] = useState<MessageView[]>([])
const [currentChatId, setCurrentChatId] = useState<string | null>(null)
const [modelId, setModelId] = useState<string | null>(null)
const [busy, setBusy] = useState(false)
const [activeRequestId, setActiveRequestId] = useState<string | null>(null)
const [error, setError] = useState('')
const streamController = useRef<AbortController | null>(null)
const resumeAttempted = useRef(new Set<string>())
const models = policy?.models ?? []
const model: ChatModel | null = models.find(item => item.id === modelId)
?? models.find(item => item.id === policy?.default_model) ?? models[0] ?? null
const refreshHistory = useCallback(async (signal?: AbortSignal) => {
if (!auth) return
const list = await apiRequest<ThreadList>('/api/v1/chat/threads', { signal })
setHistory(list.threads)
}, [auth?.account.id])
const loadThread = useCallback(async (threadId: string, signal?: AbortSignal) => {
const detail = await apiRequest<ThreadDetail>(
`/api/v1/chat/threads/${threadId}`, { signal })
setCurrentChatId(detail.thread.id); setMessages(detail.messages)
return detail
}, [])
useEffect(() => {
streamController.current?.abort()
setPolicy(null); setCredential(null); setHistory([]); setMessages([])
setCurrentChatId(null); setBusy(false); setActiveRequestId(null); setError('')
resumeAttempted.current.clear()
if (!auth) return
const controller = new AbortController()
Promise.all([
apiRequest<ChatPolicyView>('/api/v1/chat/policy', { signal: controller.signal }),
apiRequest<CredentialView>('/api/v1/chat/credential', { signal: controller.signal }),
apiRequest<ThreadList>('/api/v1/chat/threads', { signal: controller.signal }),
]).then(([p, c, h]) => {
if (controller.signal.aborted) return
setPolicy(p); setModelId(p.default_model); setCredential(c); setHistory(h.threads)
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
setError(chatErrors[data.code] ?? 'Ответ завершился с ошибкой.')
} else if (name === 'message.interrupted') {
setError(data.reason === 'stopped' ? ''
: 'Ответ был прерван. Частичный текст сохранён.')
}
})
} catch (reason) {
if (!controller.signal.aborted) setError(chatProblem(reason))
} finally {
if (streamController.current === controller) streamController.current = null
setBusy(false); setActiveRequestId(null)
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
async function send(text: string, selectedModelId?: string): Promise<boolean> {
const selectedModel = policy?.models.find(item => item.id === selectedModelId) ?? model
if (!auth || !selectedModel || busy || !credential?.verified) return false
setError(''); setBusy(true)
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
const requestId = crypto.randomUUID()
setActiveRequestId(requestId)
let accepted: ChatRequestView
try {
accepted = await apiRequest<ChatRequestView>(
`/api/v1/chat/threads/${threadId}/requests`, {
method: 'POST', csrf: auth.csrf_token,
data: { request_id: requestId, text, model: selectedModel.id }, timeoutMs: 20000,
})
} catch (reason) {
if (reason instanceof ApiError) {
setBusy(false); setActiveRequestId(null); setError(chatProblem(reason)); return false
}
try {
accepted = await apiRequest<ChatRequestView>(
`/api/v1/chat/requests/${requestId}`, { timeoutMs: 10000 })
} catch {
setBusy(false); setActiveRequestId(null)
setError('Неизвестно, принял ли сервер сообщение. Новый запрос автоматически не отправлен.')
return false
}
}
try { await loadThread(threadId); await refreshHistory() }
catch (reason) {
setBusy(false); setActiveRequestId(null); setError(chatProblem(reason)); return true
}
void streamRequest(accepted.id, threadId)
return true
}
async function stop() {
if (!auth || !activeRequestId) return
const requestId = activeRequestId
try {
await apiRequest<ChatRequestView>(
`/api/v1/chat/requests/${requestId}/stop`, {
method: 'POST', csrf: auth.csrf_token, data: {},
})
streamController.current?.abort()
if (currentChatId) await loadThread(currentChatId)
setError('')
} catch (reason) { setError(chatProblem(reason)) }
finally { setBusy(false); setActiveRequestId(null) }
}
function credentialDisabled(value: CredentialView) {
streamController.current?.abort()
setCredential(value); setBusy(false); setActiveRequestId(null)
}
return {
policy, credential, history, messages, currentChatId, model, busy, activeRequestId,
error, setError, setCredential, credentialDisabled, setModelId,
newChat, openChat, send, stop,
}
}
export type ChatRuntime = ReturnType<typeof useChatRuntime>
