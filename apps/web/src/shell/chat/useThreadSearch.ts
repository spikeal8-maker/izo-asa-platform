import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { ApiError, apiRequest, type ThreadList, type ThreadView } from '../../shared/api'

type SearchState = {
  accountId: string | undefined
  query: string
  active: boolean
  rows: ThreadView[]
  cursor: string | null
  loading: boolean
  error: string
  invalid: boolean
  retryCursor: string | null
  dirty: boolean
}
const empty = (accountId: string | undefined): SearchState => ({ accountId, query: '', active: false,
  rows: [], cursor: null, loading: false, error: '', invalid: false, retryCursor: null, dirty: false })

function queryProblem(query: string) {
  if (Array.from(query).length > 256) return 'Введите не больше 256 символов для поиска.'
  if (/[\u0000\uD800-\uDFFF]/u.test(query)) return 'Удалите недопустимые символы из строки поиска.'
  return ''
}
function searchProblem(reason: unknown) {
  if (reason instanceof ApiError) {
    if (reason.code === 'search_unavailable') return 'Поиск временно недоступен. Повторите попытку.'
    if (reason.code === 'invalid_thread_cursor') return 'Результаты изменились. Повторите поиск с первой страницы.'
    if (reason.status === 422 || reason.code === 'invalid_input') return 'Проверьте строку поиска: не больше 256 символов.'
    if (reason.status === 401) return 'Войдите в аккаунт, чтобы искать чаты.'
  }
  return 'Не удалось выполнить поиск. Проверьте соединение и повторите.'
}

export function useThreadSearch(accountId: string | undefined) {
  const [stored, setStored] = useState<SearchState>(() => empty(accountId))
  const state = useRef(stored)
  const currentAccount = useRef(accountId)
  currentAccount.current = accountId
  const generation = useRef(0)
  const pending = useRef<AbortController | null>(null)
  const publish = useCallback((next: SearchState) => { state.current = next; setStored(next) }, [])
  const cancel = useCallback(() => {
    generation.current++
    pending.current?.abort()
    pending.current = null
  }, [])
  const resetSearch = useCallback(() => {
    cancel()
    publish(empty(currentAccount.current))
  }, [cancel, publish])
  useEffect(() => {
    if (state.current.accountId !== accountId) resetSearch()
  }, [accountId, resetSearch])
  useEffect(() => () => cancel(), [cancel])

  const read = useCallback(async (cursor: string | null) => {
    const source = state.current
    if (!source.accountId || source.accountId !== currentAccount.current || !source.active || source.invalid) return
    cancel()
    const controller = new AbortController(), started = generation.current
    pending.current = controller
    const current = () => !controller.signal.aborted && pending.current === controller
      && currentAccount.current === source.accountId && state.current.accountId === source.accountId
      && state.current.query === source.query && generation.current === started
    publish({ ...source, rows: cursor ? source.rows : [], cursor: cursor ? source.cursor : null,
      loading: true, error: '', dirty: false, retryCursor: cursor })
    const params = new URLSearchParams({ q: source.query })
    if (cursor) params.set('cursor', cursor)
    try {
      const page = await apiRequest<ThreadList>(`/api/v1/chat/threads?${params}`, { signal: controller.signal })
      if (!current()) return
      const previous = cursor ? state.current.rows : [], known = new Set(previous.map(row => row.id))
      publish({ ...state.current, rows: [...previous, ...page.threads.filter(row => !known.has(row.id))],
        cursor: page.next_cursor ?? null, loading: false, retryCursor: null })
    } catch (reason) {
      if (!current()) return
      const unauthorized = reason instanceof ApiError && reason.status === 401
      publish({ ...state.current, loading: false, error: searchProblem(reason),
        rows: unauthorized ? [] : state.current.rows, cursor: unauthorized ? null : state.current.cursor,
        retryCursor: unauthorized || reason instanceof ApiError && reason.code === 'invalid_thread_cursor' ? null : cursor })
    } finally {
      if (pending.current === controller) pending.current = null
    }
  }, [cancel, publish])

  const setQuery = useCallback((query: string) => {
    if (state.current.accountId === currentAccount.current && state.current.query === query) return
    cancel()
    const error = queryProblem(query)
    publish({ ...empty(currentAccount.current), query, active: Boolean(query.trim() || error),
      error, invalid: Boolean(error) })
    void read(null)
  }, [cancel, publish, read])
  const invalidateSearch = useCallback((renamed?: ThreadView) => {
    const source = state.current
    if (!source.active || source.accountId !== currentAccount.current || source.invalid) return
    cancel()
    // Keep the editor's row mounted until its confirmed save has closed the form.
    publish({ ...source, loading: false, error: '', dirty: true,
      rows: renamed ? source.rows.map(row => row.id === renamed.id ? renamed : row) : source.rows })
  }, [cancel, publish])
  const refresh = useCallback(() => { void read(null) }, [read])
  const retry = useCallback(() => { if (!pending.current) void read(state.current.retryCursor) }, [read])
  const loadMore = useCallback(() => {
    if (state.current.cursor && !pending.current && !state.current.error) void read(state.current.cursor)
  }, [read])
  const visible = stored.accountId === accountId ? stored : empty(accountId)
  return { search: { ...visible, setQuery, refresh, retry, loadMore }, resetSearch, invalidateSearch }
}
export type ThreadSearch = ReturnType<typeof useThreadSearch>['search']

/** Preserve the ordinary list's reading position and settle Rename before requerying. */
export function useThreadSearchView(search: ThreadSearch, editingId: string | null,
  historyList: RefObject<HTMLDivElement | null>, closeRename: (restore: boolean) => void) {
  const searchButton = useRef<HTMLButtonElement>(null)
  const searchInput = useRef<HTMLInputElement>(null)
  const historyScroll = useRef(0)
  const wasSearching = useRef(false)
  const focusedRow = useRef<HTMLElement | null>(null)
  useEffect(() => { if (search.dirty && !editingId) search.refresh() }, [search.dirty, editingId, search.refresh])
  useLayoutEffect(() => {
    if (historyList.current && (search.active || wasSearching.current))
      historyList.current.scrollTop = search.active ? 0 : historyScroll.current
    wasSearching.current = search.active
  }, [search.query, search.active, historyList])
  useLayoutEffect(() => {
    if (search.active && focusedRow.current && !focusedRow.current.isConnected
        && document.activeElement === document.body) searchInput.current?.focus({ preventScroll: true })
  }, [search.rows, search.active])
  function changeSearch(query: string) {
    if (!search.active) historyScroll.current = historyList.current?.scrollTop ?? 0
    if (query !== search.query) closeRename(false)
    search.setQuery(query)
  }
  return { searchButton, searchInput, changeSearch, historyScroll, focusedRow }
}
