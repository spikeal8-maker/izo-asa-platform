import { useLayoutEffect, useRef } from 'react'

const bottomDistance = 48

export function useChatScroll(ownerId: string | undefined, threadId: string | null, content: readonly unknown[]) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const owner = useRef(ownerId)
  const positions = useRef(new Map<string, { top: number; atBottom: boolean }>())
  const shownThread = useRef<string | null>(null)
  const atBottom = useRef(true)
  const prepend = useRef<{ threadId: string; height: number; top: number } | null>(null)

  function nearBottom(node: HTMLElement) {
    return node.scrollHeight - node.clientHeight - node.scrollTop <= bottomDistance
  }

  function remember() {
    const node = scrollRef.current
    if (node && shownThread.current) {
      atBottom.current = nearBottom(node)
      positions.current.set(shownThread.current, { top: node.scrollTop, atBottom: atBottom.current })
    }
  }

  function onScroll() {
    const node = scrollRef.current
    if (!node) return
    atBottom.current = nearBottom(node)
    remember()
  }

  function preparePrepend() {
    const node = scrollRef.current
    if (node && shownThread.current) {
      prepend.current = { threadId: shownThread.current, height: node.scrollHeight, top: node.scrollTop }
    }
  }

  useLayoutEffect(() => {
    if (owner.current === ownerId) return
    owner.current = ownerId
    positions.current.clear()
    prepend.current = null
    shownThread.current = null
    atBottom.current = true
  }, [ownerId])

  useLayoutEffect(() => {
    const node = scrollRef.current
    if (shownThread.current !== threadId) {
      prepend.current = null
      shownThread.current = threadId
      const saved = threadId ? positions.current.get(threadId) : undefined
      atBottom.current = saved?.atBottom ?? true
      if (node) node.scrollTop = atBottom.current ? node.scrollHeight : saved?.top ?? 0
    } else if (node && prepend.current?.threadId === threadId) {
      const anchor = prepend.current
      prepend.current = null
      node.scrollTop = anchor.top + node.scrollHeight - anchor.height
      atBottom.current = false
      remember()
    } else if (node && atBottom.current) {
      node.scrollTop = node.scrollHeight
    }
  }, [ownerId, threadId, content])

  useLayoutEffect(() => {
    const node = scrollRef.current
    if (!node) return
    const observer = new ResizeObserver(() => {
      if (atBottom.current) node.scrollTop = node.scrollHeight
    })
    observer.observe(node)
    if (node.firstElementChild) observer.observe(node.firstElementChild)
    return () => observer.disconnect()
  }, [threadId, content.length > 0])

  return { scrollRef, onScroll, remember, preparePrepend }
}
