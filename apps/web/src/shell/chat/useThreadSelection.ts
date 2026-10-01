import { useCallback, useRef, useState } from 'react'
import { apiRequest, type MessageView, type ThreadDetail, type ThreadList, type ThreadView } from '../../shared/api'
import { chatProblem, lastChatWarning } from './chatAttachments'

type Selection = { accountId: string | undefined; threadId: string | null; version: number }

export function useThreadSelection(accountId: string | undefined, update: {
  chatId: (value: string | null) => void
  messages: (value: MessageView[]) => void
  history: (value: ThreadView[]) => void
  error: (value: string) => void
}) {
  const currentAccount = useRef(accountId)
  currentAccount.current = accountId
  const selection = useRef<Selection>({ accountId, threadId: null, version: 0 })
  const [openingThread, setOpeningThread] = useState(false)

  const selectThread = useCallback((threadId: string | null) => {
    selection.current = { accountId: currentAccount.current, threadId, version: selection.current.version + 1 }
  }, [])
  const selected = useCallback((threadId: string, at: Selection) =>
    selection.current === at && currentAccount.current === at.accountId && at.threadId === threadId, [])

  const refreshHistory = useCallback(async (signal?: AbortSignal) => {
    if (!accountId) return
    const list = await apiRequest<ThreadList>('/api/v1/chat/threads', { signal })
    if (currentAccount.current === accountId) update.history(list.threads)
  }, [accountId, update.history])

  const loadThread = useCallback(async (threadId: string, signal?: AbortSignal) => {
    const at = selection.current
    try {
      const detail = await apiRequest<ThreadDetail>(`/api/v1/chat/threads/${threadId}`, { signal })
      if (!selected(threadId, at)) return null
      update.chatId(detail.thread.id)
      update.messages(detail.messages)
      const warning = await lastChatWarning(detail.messages, signal)
      if (warning && selected(threadId, at)) update.error(warning)
      return detail
    } catch (reason) {
      if (!selected(threadId, at)) return null
      throw reason
    }
  }, [selected, update.chatId, update.messages, update.error])

  const resetSelection = useCallback(() => {
    selectThread(null)
    setOpeningThread(false)
  }, [selectThread])
  const openThread = useCallback(async (threadId: string, previousId: string | null) => {
    selectThread(threadId)
    const at = selection.current
    setOpeningThread(true)
    update.error('')
    let latest = false
    try {
      const detail = await loadThread(threadId)
      latest = Boolean(detail && selected(threadId, at))
      return latest
    } catch (reason) {
      if (selected(threadId, at)) {
        selectThread(previousId)
        update.error(`Не удалось открыть чат. ${chatProblem(reason)}`)
        latest = true
      }
      return false
    } finally {
      if (latest) setOpeningThread(false)
    }
  }, [loadThread, selectThread, selected, update.error])
  const canSendTo = (threadId: string | null, owner: string) =>
    !openingThread && selection.current.accountId === owner && selection.current.threadId === threadId

  return { selection, selectThread, selected, loadThread, refreshHistory,
    openingThread, resetSelection, openThread, canSendTo }
}
