import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest, type ThreadList, type ThreadView } from '../../shared/api'
import { chatProblem } from './chatAttachments'

export function useThreadHistory(accountId: string | undefined, setError: (value: string) => void) {
  const [history, setHistory] = useState<ThreadView[]>([])
  const [historyCursor, setHistoryCursor] = useState<string | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [renamingThreadId, setRenamingThreadId] = useState<string | null>(null)
  const pending = useRef<AbortController | null>(null)
  const refreshing = useRef<AbortController | null>(null)
  const renaming = useRef<AbortController | null>(null)
  const revision = useRef(0)
  const loadedEarlier = useRef(false)
  const currentAccount = useRef(accountId)
  currentAccount.current = accountId

  const cancelHistoryLoad = useCallback(() => {
    pending.current?.abort()
    pending.current = null
    setLoadingHistory(false)
  }, [])
  const resetHistory = useCallback(() => {
    revision.current++
    loadedEarlier.current = false
    cancelHistoryLoad()
    refreshing.current?.abort()
    refreshing.current = null
    renaming.current?.abort()
    renaming.current = null
    setRenamingThreadId(null)
    setHistory([])
    setHistoryCursor(null)
  }, [cancelHistoryLoad])
  useEffect(() => () => {
    pending.current?.abort()
    pending.current = null
    refreshing.current?.abort()
    refreshing.current = null
    renaming.current?.abort()
    renaming.current = null
    revision.current++
  }, [])
  const refreshHistory = useCallback(async (signal?: AbortSignal) => {
    if (!accountId) return
    cancelHistoryLoad()
    refreshing.current?.abort()
    const controller = new AbortController()
    refreshing.current = controller
    const started = revision.current
    const abort = () => controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) controller.abort()
    try {
      const page = await apiRequest<ThreadList>('/api/v1/chat/threads', { signal: controller.signal })
      if (controller.signal.aborted || currentAccount.current !== accountId
          || started !== revision.current || renaming.current) return
      const keepEarlier = loadedEarlier.current
      const latest = new Set(page.threads.map(thread => thread.id))
      setHistory(current => keepEarlier
        ? [...page.threads, ...current.filter(thread => !latest.has(thread.id))] : page.threads)
      if (!keepEarlier) setHistoryCursor(page.next_cursor ?? null)
    } catch (reason) {
      if (!controller.signal.aborted && currentAccount.current === accountId
          && started === revision.current && !renaming.current) throw reason
    } finally {
      signal?.removeEventListener('abort', abort)
      if (refreshing.current === controller) refreshing.current = null
    }
  }, [accountId, cancelHistoryLoad])
  const loadMoreHistory = useCallback(async () => {
    if (!accountId || !historyCursor || pending.current || refreshing.current) return
    const controller = new AbortController()
    const started = revision.current
    pending.current = controller
    setLoadingHistory(true)
    try {
      const page = await apiRequest<ThreadList>(
        `/api/v1/chat/threads?cursor=${encodeURIComponent(historyCursor)}`,
        { signal: controller.signal })
      if (controller.signal.aborted || currentAccount.current !== accountId
          || started !== revision.current || renaming.current) return
      loadedEarlier.current = true
      setHistory(current => {
        const known = new Set(current.map(thread => thread.id))
        return [...current, ...page.threads.filter(thread => !known.has(thread.id))]
      })
      setHistoryCursor(page.next_cursor ?? null)
    } catch (reason) {
      if (!controller.signal.aborted && currentAccount.current === accountId
          && started === revision.current && !renaming.current)
        setError(`Не удалось загрузить ранние чаты. ${chatProblem(reason)}`)
    } finally {
      if (pending.current === controller) {
        pending.current = null
        if (currentAccount.current === accountId) setLoadingHistory(false)
      }
    }
  }, [accountId, historyCursor, setError])

  const renameThread = useCallback(async (threadId: string, title: string, csrf: string) => {
    if (!accountId || renaming.current) return false
    const controller = new AbortController()
    renaming.current = controller
    revision.current++
    setRenamingThreadId(threadId)
    try {
      const thread = await apiRequest<ThreadView>(`/api/v1/chat/threads/${threadId}`, {
        method: 'PATCH', csrf, data: { title }, signal: controller.signal,
      })
      if (controller.signal.aborted || currentAccount.current !== accountId
          || renaming.current !== controller) return false
      revision.current++
      setHistory(current => current.map(item => item.id === threadId ? { ...item, title: thread.title } : item))
      return true
    } finally {
      if (renaming.current === controller) {
        renaming.current = null
        if (currentAccount.current === accountId) setRenamingThreadId(null)
      }
    }
  }, [accountId])

  return { history, historyCursor, loadingHistory, renamingThreadId, renameThread,
    resetHistory, loadMoreHistory, refreshHistory }
}
