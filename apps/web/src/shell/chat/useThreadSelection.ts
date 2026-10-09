import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { apiRequest, type MessagePage, type MessageView, type ThreadDetail, type ThreadList, type ThreadView } from '../../shared/api'
import { chatProblem, lastChatWarning } from './chatAttachments'

export type Selection = { accountId: string | undefined; threadId: string | null; version: number }

export function useThreadSelection(accountId: string | undefined, update: {
  chatId: (value: string | null) => void
  messages: Dispatch<SetStateAction<MessageView[]>>
  history: (value: ThreadView[]) => void
  historyCursor: (value: string | null) => void
  error: (value: string) => void
}) {
  const currentAccount = useRef(accountId)
  currentAccount.current = accountId
  const selection = useRef<Selection>({ accountId, threadId: null, version: 0 })
  const resumeClaims = useRef(new Set<string>())
  const [openingThread, setOpeningThread] = useState(false)
  const [olderCursor, setOlderCursor] = useState<number | null>(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const loadedThread = useRef<string | null>(null)
  const pendingOlder = useRef<{ at: Selection; controller: AbortController } | null>(null)

  const selectThread = useCallback((threadId: string | null) => {
    pendingOlder.current?.controller.abort()
    pendingOlder.current = null
    selection.current = { accountId: currentAccount.current, threadId, version: selection.current.version + 1 }
  }, [])
  const selected = useCallback((threadId: string, at: Selection) =>
    selection.current === at && currentAccount.current === at.accountId && at.threadId === threadId, [])
  const claimResume = (threadId: string, requestId: string) => {
    const at = selection.current
    const key = `${requestId}:${at.version}`
    if (!selected(threadId, at) || resumeClaims.current.has(requestId) || resumeClaims.current.has(key)) return null
    resumeClaims.current.add(key)
    return { current: () => selected(threadId, at), release: () => resumeClaims.current.delete(key) }
  }
  const clearResumeClaims = () => resumeClaims.current.clear()
  const stopResume = (requestId: string) => resumeClaims.current.add(requestId)

  const refreshHistory = useCallback(async (signal?: AbortSignal) => {
    if (!accountId) return
    const list = await apiRequest<ThreadList>('/api/v1/chat/threads', { signal })
    if (currentAccount.current === accountId) update.history(list.threads)
    if (currentAccount.current === accountId) update.historyCursor(list.next_cursor ?? null)
  }, [accountId, update.history, update.historyCursor])

  const loadThread = useCallback(async (threadId: string, signal?: AbortSignal) => {
    const at = selection.current
    try {
      const detail = await apiRequest<ThreadDetail>(`/api/v1/chat/threads/${threadId}`, { signal })
      if (!selected(threadId, at)) return null
      update.chatId(detail.thread.id)
      if (loadedThread.current === threadId) {
        update.messages(current => {
          const known = new Set(detail.messages.map(message => message.id))
          return [...current.filter(message => !known.has(message.id)), ...detail.messages]
            .sort((a, b) => a.sequence - b.sequence)
        })
      } else {
        loadedThread.current = threadId
        setOlderCursor(detail.next_before_sequence ?? null)
        update.messages(detail.messages)
      }
      const warning = await lastChatWarning(detail.messages, signal)
      if (warning && selected(threadId, at)) update.error(warning)
      return detail
    } catch (reason) {
      if (!selected(threadId, at)) return null
      throw reason
    }
  }, [selected, update.chatId, update.messages, update.error])

  const loadOlder = useCallback(async (threadId: string, beforePrepend: () => void) => {
    const at = selection.current
    const cursor = olderCursor
    if (!selected(threadId, at) || cursor === null || pendingOlder.current?.at === at) return
    const pending = { at, controller: new AbortController() }
    pendingOlder.current = pending
    setLoadingOlder(true)
    try {
      const page = await apiRequest<MessagePage>(
        `/api/v1/chat/threads/${threadId}/messages?before_sequence=${cursor}`,
        { signal: pending.controller.signal })
      if (!selected(threadId, at)) return
      if (page.messages.length) {
        beforePrepend()
        update.messages(current => {
          const known = new Set(current.map(message => message.id))
          return [...page.messages.filter(message => !known.has(message.id)), ...current]
            .sort((a, b) => a.sequence - b.sequence)
        })
      }
      setOlderCursor(page.next_before_sequence)
    } catch (reason) {
      if (selected(threadId, at)) update.error(`Не удалось загрузить ранние сообщения. ${chatProblem(reason)}`)
    } finally {
      if (pendingOlder.current === pending) {
        pendingOlder.current = null
        if (selected(threadId, at)) setLoadingOlder(false)
      }
    }
  }, [olderCursor, selected, update.messages, update.error])

  const resetSelection = useCallback(() => {
    selectThread(null)
    loadedThread.current = null
    setOlderCursor(null)
    setLoadingOlder(false)
    setOpeningThread(false)
  }, [selectThread])
  const openThread = useCallback(async (threadId: string, previousId: string | null) => {
    const previousCursor = olderCursor
    selectThread(threadId)
    if (threadId !== previousId) setOlderCursor(null)
    setLoadingOlder(false)
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
        setOlderCursor(previousCursor)
        update.error(`Не удалось открыть чат. ${chatProblem(reason)}`)
        latest = true
      }
      return false
    } finally {
      if (latest) setOpeningThread(false)
    }
  }, [loadThread, olderCursor, selectThread, selected, update.error])
  const canSendTo = (threadId: string | null, owner: string) =>
    !openingThread && selection.current.accountId === owner && selection.current.threadId === threadId

  return { selection, selectThread, selected, loadThread, loadOlder, olderCursor, loadingOlder, refreshHistory,
    openingThread, resetSelection, openThread, canSendTo, claimResume, clearResumeClaims, stopResume }
}
