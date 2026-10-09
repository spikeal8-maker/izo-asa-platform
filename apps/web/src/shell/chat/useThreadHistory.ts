import { useCallback, useRef, useState } from 'react'
import { apiRequest, type ThreadList, type ThreadView } from '../../shared/api'
import { chatProblem } from './chatAttachments'

export function useThreadHistory(accountId: string | undefined, setError: (value: string) => void) {
  const [history, setHistory] = useState<ThreadView[]>([])
  const [historyCursor, setHistoryCursor] = useState<string | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const pending = useRef<AbortController | null>(null)
  const currentAccount = useRef(accountId)
  currentAccount.current = accountId

  const cancelHistoryLoad = useCallback(() => {
    pending.current?.abort()
    pending.current = null
    setLoadingHistory(false)
  }, [])
  const resetHistory = useCallback(() => {
    cancelHistoryLoad()
    setHistory([])
    setHistoryCursor(null)
  }, [cancelHistoryLoad])
  const loadMoreHistory = useCallback(async () => {
    if (!accountId || !historyCursor || pending.current) return
    const controller = new AbortController()
    pending.current = controller
    setLoadingHistory(true)
    try {
      const page = await apiRequest<ThreadList>(
        `/api/v1/chat/threads?cursor=${encodeURIComponent(historyCursor)}`,
        { signal: controller.signal })
      if (controller.signal.aborted || currentAccount.current !== accountId) return
      setHistory(current => {
        const known = new Set(current.map(thread => thread.id))
        return [...current, ...page.threads.filter(thread => !known.has(thread.id))]
      })
      setHistoryCursor(page.next_cursor ?? null)
    } catch (reason) {
      if (!controller.signal.aborted && currentAccount.current === accountId)
        setError(`Не удалось загрузить ранние чаты. ${chatProblem(reason)}`)
    } finally {
      if (pending.current === controller) {
        pending.current = null
        if (currentAccount.current === accountId) setLoadingHistory(false)
      }
    }
  }, [accountId, historyCursor, setError])

  return { history, setHistory, historyCursor, setHistoryCursor, loadingHistory,
    cancelHistoryLoad, resetHistory, loadMoreHistory }
}
