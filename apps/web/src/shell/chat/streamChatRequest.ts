import type { RefObject, Dispatch, SetStateAction } from 'react'
import { apiStream, chatProviderProblem, type MessageView } from '../../shared/api'
import { consumeSse } from './useChatCatalog'
import { chatProblem } from './chatAttachments'
import type { Selection } from './useThreadSelection'

type StreamContext = {
  selection: RefObject<Selection>
  selected: (threadId: string, at: Selection) => boolean
  streamController: RefObject<AbortController | null>
  setBusy: Dispatch<SetStateAction<boolean>>
  setActiveRequestId: Dispatch<SetStateAction<string | null>>
  setMessages: Dispatch<SetStateAction<MessageView[]>>
  setError: Dispatch<SetStateAction<string>>
  idle: () => void
  loadThread: (threadId: string) => Promise<unknown>
  refreshHistory: () => Promise<unknown>
}

export async function streamChatRequest(requestId: string, threadId: string, context: StreamContext) {
  const { selection, selected, streamController, setBusy, setActiveRequestId,
    setMessages, setError, idle, loadThread, refreshHistory } = context
  const controller = new AbortController()
  const at = selection.current
  streamController.current?.abort(); streamController.current = controller
  setBusy(true); setActiveRequestId(requestId)
  setMessages(current => current.map(message =>
    message.request_id === requestId && message.role === 'assistant'
      ? { ...message, content: '', state: 'partial' } : message))
  try {
    const response = await apiStream(`/api/v1/chat/requests/${requestId}/events`, controller.signal)
    await consumeSse(response, (name, data) => {
      if (!selected(threadId, at)) return
      if (name === 'text.delta' && typeof data.text === 'string') {
        setMessages(current => current.map(message =>
          message.request_id === requestId && message.role === 'assistant'
            ? { ...message, content: message.content + data.text, state: 'partial' } : message))
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
    if (!controller.signal.aborted && selected(threadId, at)) setError(chatProblem(reason))
  } finally {
    if (streamController.current === controller) {
      streamController.current = null
      if (selected(threadId, at)) idle()
    }
    if (selected(threadId, at)) {
      try { await loadThread(threadId); await refreshHistory() }
      catch (reason) { if (selected(threadId, at)) setError(current => current || chatProblem(reason)) }
    }
  }
}
