import { useCallback, useEffect, useRef, useState } from 'react'
import {
  apiRequest, apiStream, ApiError, type AuthView, type ChatPolicyView,
  type ChatRequestView, type CredentialView, type MessageView,
  type ThreadDetail, type ThreadList, type ThreadView,
} from '../shared/api'
import { Icon } from '../shared/ui/Icon'
import { Link } from './router'
import { ChatComposer } from './chat/ChatComposer'
import { ChatMessage } from './chat/ChatMessage'
import { ChatSidebar } from './chat/ChatSidebar'
import { selectedModel } from './chat/modelCatalog'
import type { ChatModel } from './chat/types'
import { useVisualViewport } from './chat/useVisualViewport'
import './chat.css'

const desktopQuery = '(min-width: 1120px)'
const errors: Record<string, string> = {
  chat_preview_not_enabled: 'Этот аккаунт не допущен к локальному Chat preview.',
  credential_not_verified: 'Подключите и проверьте ключ DeepSeek.',
  credential_rejected: 'DeepSeek отклонил этот ключ.',
  credential_storage_unavailable: 'Хранилище ключей недоступно. Проверьте локальный root key.',
  credential_unavailable: 'Сохранённый ключ недоступен или был отключён.',
  credential_revision_conflict: 'Настройки ключа уже изменились. Обновите страницу.',
  credential_in_use: 'Сначала остановите активный ответ, затем замените ключ.',
  model_not_allowed: 'Выбранная модель не разрешена сервером.',
  active_request_exists: 'В этом чате уже выполняется ответ.',
  request_conflict: 'Повторный запрос имеет другие параметры.',
  chat_rate_limited: 'Достигнут временный лимит Chat. Повторите позднее.',
  provider_rate_limited: 'DeepSeek ограничил частоту запросов.',
  provider_balance: 'DeepSeek не разрешил запрос для этого ключа.',
  provider_unavailable: 'DeepSeek сейчас недоступен.',
  provider_overloaded: 'DeepSeek перегружен. Автоматический повтор не выполнялся.',
  provider_stream_interrupted: 'Поток DeepSeek прервался. Частичный ответ сохранён.',
  request_expired: 'Время выполнения запроса истекло.',
  executor_restarted: 'Исполнитель был перезапущен. Частичный ответ сохранён.',
}

function chatProblem(reason: unknown): string {
  if (reason instanceof ApiError) return errors[reason.code]
    ?? (reason.status === 401 ? 'Войдите в аккаунт.'
      : 'Сервер отклонил Chat-запрос.')
  if (reason instanceof DOMException && reason.name === 'AbortError') return ''
  return 'Связь с Chat прервалась. Новый платный запрос автоматически не запускался.'
}

type StreamPayload = Record<string, unknown>
async function consumeSse(response: Response, onEvent: (name: string, data: StreamPayload) => void) {
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
    buffer += decoder.decode()
  } finally {
    reader.releaseLock()
  }
}
export function ChatPage({ auth, theme, onThemeChange, onLogout }: {
  auth: AuthView | null | undefined
  theme: 'light' | 'dark'
  onThemeChange: (value: 'light' | 'dark') => void
  onLogout: () => void
}) {
  const [policy, setPolicy] = useState<ChatPolicyView | null>(null)
  const [credential, setCredential] = useState<CredentialView | null>(null)
  const [history, setHistory] = useState<ThreadView[]>([])
  const [messages, setMessages] = useState<MessageView[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [modelId, setModelId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [setupOpen, setSetupOpen] = useState(true)
  const [setupBusy, setSetupBusy] = useState(false)
  const [keyInput, setKeyInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(
    () => window.matchMedia(desktopQuery).matches)
  const streamController = useRef<AbortController | null>(null)
  const resumeAttempted = useRef(new Set<string>())

  useVisualViewport()
  const model = selectedModel(policy, modelId)

  const refreshHistory = useCallback(async (signal?: AbortSignal) => {
    if (!auth) return
    const list = await apiRequest<ThreadList>('/api/v1/chat/threads', { signal })
    setHistory(list.threads)
  }, [auth?.account.id])

  const loadThread = useCallback(async (threadId: string, signal?: AbortSignal) => {
    const detail = await apiRequest<ThreadDetail>(
      `/api/v1/chat/threads/${threadId}`, { signal })
    setCurrentChatId(detail.thread.id)
    setMessages(detail.messages)
    return detail
  }, [])

  useEffect(() => {
    const media = window.matchMedia(desktopQuery)
    const syncSidebarMode = () => setSidebarOpen(media.matches)
    syncSidebarMode()
    media.addEventListener('change', syncSidebarMode)
    return () => media.removeEventListener('change', syncSidebarMode)
  }, [])

  useEffect(() => {
    streamController.current?.abort()
    setPolicy(null); setCredential(null); setHistory([]); setMessages([])
    setCurrentChatId(null); setBusy(false); setActiveRequestId(null); setError('')
    setKeyInput(''); resumeAttempted.current.clear()
    if (!auth) return
    const controller = new AbortController()
    Promise.all([
      apiRequest<ChatPolicyView>('/api/v1/chat/policy', { signal: controller.signal }),
      apiRequest<CredentialView>('/api/v1/chat/credential', { signal: controller.signal }),
      apiRequest<ThreadList>('/api/v1/chat/threads', { signal: controller.signal }),
    ]).then(([nextPolicy, nextCredential, nextHistory]) => {
      if (controller.signal.aborted) return
      setPolicy(nextPolicy)
      setModelId(nextPolicy.default_model)
      setCredential(nextCredential)
      setSetupOpen(!nextCredential.verified)
      setHistory(nextHistory.threads)
    }).catch(reason => {
      if (!controller.signal.aborted) setError(chatProblem(reason))
    })
    return () => controller.abort()
  }, [auth?.account.id])

  useEffect(() => () => streamController.current?.abort(), [])
  const streamRequest = useCallback(async (requestId: string, threadId: string) => {
    const controller = new AbortController()
    streamController.current?.abort()
    streamController.current = controller
    setBusy(true)
    setActiveRequestId(requestId)
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
          setError(errors[data.code] ?? 'Ответ завершился с ошибкой.')
        } else if (name === 'message.interrupted') {
          setError(data.reason === 'stopped' ? '' : 'Ответ был прерван. Частичный текст сохранён.')
        }
      })
    } catch (reason) {
      if (!controller.signal.aborted) setError(chatProblem(reason))
    } finally {
      if (streamController.current === controller) streamController.current = null
      setBusy(false)
      setActiveRequestId(null)
      try {
        await loadThread(threadId)
        await refreshHistory()
      } catch (reason) {
        setError(current => current || chatProblem(reason))
      }
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
      if (request.state === 'pending' || request.state === 'streaming') {
        void streamRequest(request.id, currentChatId)
      } else {
        void loadThread(currentChatId)
      }
    }).catch(reason => {
      if (!controller.signal.aborted) setError(chatProblem(reason))
    })
    return () => controller.abort()
  }, [auth?.account.id, busy, currentChatId, messages, loadThread, streamRequest])

  function newChat() {
    if (busy) return
    setCurrentChatId(null)
    setMessages([])
    setError('')
    if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
  }

  async function openChat(chat: ThreadView) {
    if (busy) return
    setError('')
    try {
      await loadThread(chat.id)
      if (!window.matchMedia(desktopQuery).matches) setSidebarOpen(false)
    } catch (reason) {
      setError(chatProblem(reason))
    }
  }
  async function send(text: string): Promise<boolean> {
    if (!auth || !model || busy || !credential?.verified) return false
    setError('')
    setBusy(true)
    let threadId = currentChatId
    try {
      if (!threadId) {
        const thread = await apiRequest<ThreadView>('/api/v1/chat/threads', {
          method: 'POST', csrf: auth.csrf_token, data: { title: null },
        })
        threadId = thread.id
        setCurrentChatId(threadId)
      }
    } catch (reason) {
      setBusy(false)
      setError(chatProblem(reason))
      return false
    }

    const requestId = crypto.randomUUID()
    setActiveRequestId(requestId)
    let accepted: ChatRequestView | null = null
    try {
      accepted = await apiRequest<ChatRequestView>(
        `/api/v1/chat/threads/${threadId}/requests`, {
          method: 'POST', csrf: auth.csrf_token,
          data: { request_id: requestId, text, model: model.id },
          timeoutMs: 20000,
        })
    } catch (reason) {
      if (reason instanceof ApiError) {
        setBusy(false); setActiveRequestId(null); setError(chatProblem(reason))
        return false
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

    try {
      await loadThread(threadId)
      await refreshHistory()
    } catch (reason) {
      setBusy(false); setActiveRequestId(null); setError(chatProblem(reason))
      return true
    }
    setBusy(false)
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
    } catch (reason) {
      setError(chatProblem(reason))
    } finally {
      setBusy(false)
      setActiveRequestId(null)
    }
  }

  async function verifyStored(view: CredentialView) {
    if (!auth || !view.revision) return
    const verified = await apiRequest<CredentialView>('/api/v1/chat/credential/verify', {
      method: 'POST', csrf: auth.csrf_token,
      data: { operation_id: crypto.randomUUID(), expected_revision: view.revision },
      timeoutMs: 20000,
    })
    setCredential(verified)
    setSetupOpen(!verified.verified)
  }

  async function saveAndVerify(event: React.FormEvent) {
    event.preventDefault()
    if (!auth || !keyInput.trim() || setupBusy) return
    setSetupBusy(true); setError('')
    try {
      const saved = await apiRequest<CredentialView>('/api/v1/chat/credential', {
        method: 'POST', csrf: auth.csrf_token,
        data: {
          operation_id: crypto.randomUUID(), key: keyInput.trim(),
          expected_revision: credential?.revision ?? null,
        },
      })
      setKeyInput('')
      setCredential(saved)
      await verifyStored(saved)
    } catch (reason) {
      setKeyInput('')
      setError(chatProblem(reason))
    } finally {
      setSetupBusy(false)
    }
  }

  async function verifyAgain() {
    if (!credential || setupBusy) return
    setSetupBusy(true); setError('')
    try { await verifyStored(credential) }
    catch (reason) { setError(chatProblem(reason)) }
    finally { setSetupBusy(false) }
  }

  async function disableCredential() {
    if (!auth || !credential?.revision || setupBusy) return
    setSetupBusy(true); setError('')
    try {
      const disabled = await apiRequest<CredentialView>('/api/v1/chat/credential/disable', {
        method: 'POST', csrf: auth.csrf_token,
        data: { operation_id: crypto.randomUUID(), expected_revision: credential.revision },
      })
      streamController.current?.abort()
      setCredential(disabled); setSetupOpen(true); setBusy(false); setActiveRequestId(null)
    } catch (reason) {
      setError(chatProblem(reason))
    } finally {
      setSetupBusy(false)
    }
  }
  const empty = messages.length === 0
  const chatDisabled = !auth || !policy || !credential?.verified

  return <section className={`chat-page ${empty ? 'is-empty' : ''} ${sidebarOpen ? 'sidebar-open' : ''}`}
    aria-label="Чат ИЗО АСА">
    <ChatSidebar
      auth={auth} history={history} currentChatId={currentChatId} busy={busy}
      theme={theme} onThemeChange={onThemeChange} onLogout={onLogout}
      onNewChat={newChat} onOpenChat={chat => void openChat(chat)}
      onClose={() => setSidebarOpen(false)}
    />
    {sidebarOpen && <button className="chat-drawer-backdrop" aria-label="Закрыть историю"
      onClick={() => setSidebarOpen(false)} />}

    <div className="chat-main">
      <div className="chat-toolbar">
        {!sidebarOpen && <button className="chat-icon-button chat-sidebar-open"
          aria-label="Открыть панель" onClick={() => setSidebarOpen(true)}>
          <Icon name="panel" />
        </button>}
        {auth && <button type="button" className="chat-credential-toggle"
          aria-expanded={setupOpen} onClick={() => setSetupOpen(value => !value)}>
          <span className={credential?.verified ? 'is-ok' : ''} />
          {credential?.verified ? 'DeepSeek подключён' : 'Подключить DeepSeek'}
        </button>}
        {auth && setupOpen && <form className="chat-credential-popover"
          onSubmit={event => void saveAndVerify(event)}>
          <h2>Ключ DeepSeek</h2>
          <p>Ключ сохраняется зашифрованным в этом аккаунте и не попадает в историю чата.</p>
          <input type="password" autoComplete="off" value={keyInput}
            onChange={event => setKeyInput(event.target.value)}
            aria-label="API ключ DeepSeek" placeholder="Введите API key" />
          <div className="chat-credential-actions">
            <button type="submit" disabled={setupBusy || !keyInput.trim()}>
              {credential?.configured ? 'Заменить и проверить' : 'Сохранить и проверить'}
            </button>
            {credential?.configured && !credential.verified
              && <button type="button" disabled={setupBusy} onClick={() => void verifyAgain()}>
                Проверить сохранённый
              </button>}
            {credential?.configured
              && <button type="button" className="secondary" disabled={setupBusy}
                onClick={() => void disableCredential()}>Отключить</button>}
          </div>
        </form>}
      </div>

      {empty
        ? <div className="chat-start-state">
            <h1>Чем я могу помочь?</h1>
            {auth === undefined
              ? <p className="chat-start-note" role="status">Проверяем вход…</p>
              : !auth
                ? <p className="chat-start-note">Для сохранённого разговора нужен аккаунт. <Link href="/login">Войти</Link></p>
                : !credential?.verified
                  ? <p className="chat-start-note">Подключите и проверьте свой ключ DeepSeek.</p>
                  : null}
            {error && <div className="chat-runtime-note" role="alert">
              <Icon name="info" /><span>{error}</span>
            </div>}
            <ChatComposer models={policy?.models ?? []} model={model}
              busy={busy} stoppable={Boolean(activeRequestId)} disabled={chatDisabled}
              onModelChange={(next: ChatModel) => setModelId(next.id)}
              onSend={send} onStop={() => void stop()} />
          </div>
        : <>
            <div className="chat-scroll" aria-live="polite"><div className="chat-column">
              <div className="chat-turns">
                {messages.map(message => <ChatMessage key={message.id} message={message} />)}
                {error && <div className="chat-runtime-note" role="alert">
                  <Icon name="info" /><span>{error}</span>
                </div>}
              </div>
            </div></div>
            <div className="chat-composer-dock">
              <ChatComposer models={policy?.models ?? []} model={model}
                busy={busy} stoppable={Boolean(activeRequestId)} disabled={chatDisabled}
                onModelChange={(next: ChatModel) => setModelId(next.id)}
                onSend={send} onStop={() => void stop()} />
            </div>
          </>}
    </div>
  </section>
}
