import { useLayoutEffect, useRef } from 'react'

const bottomDistance = 48

export function useChatScroll(ownerId: string | undefined, threadId: string | null, content: readonly unknown[]) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const owner = useRef(ownerId)
  const positions = useRef(new Map<string, { top: number; atBottom: boolean }>())
  const shownThread = useRef<string | null>(null)
  const atBottom = useRef(true)
  type Anchor = { threadId: string; element: HTMLElement; offset: number }
  const prepend = useRef<({ height: number; top: number } & Anchor) | null>(null)
  const readingAnchor = useRef<Anchor | null>(null)

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
      const viewport = node.getBoundingClientRect()
      const element = Array.from(node.querySelectorAll<HTMLElement>('[data-message-id]'))
        .find(item => item.getBoundingClientRect().bottom > viewport.top)
      if (element) prepend.current = {
        threadId: shownThread.current, height: node.scrollHeight, top: node.scrollTop,
        element, offset: element.getBoundingClientRect().top - viewport.top,
      }
    }
  }

  function alignReadingAnchor(node: HTMLElement) {
    const anchor = readingAnchor.current
    if (!anchor || anchor.threadId !== shownThread.current || !node.contains(anchor.element)) {
      readingAnchor.current = null
      return
    }
    const delta = anchor.element.getBoundingClientRect().top
      - node.getBoundingClientRect().top - anchor.offset
    if (Math.abs(delta) > 0.5) node.scrollTop += delta
    atBottom.current = false
    positions.current.set(anchor.threadId, { top: node.scrollTop, atBottom: false })
  }

  useLayoutEffect(() => {
    if (owner.current === ownerId) return
    owner.current = ownerId
    positions.current.clear()
    prepend.current = null
    readingAnchor.current = null
    shownThread.current = null
    atBottom.current = true
  }, [ownerId])

  useLayoutEffect(() => {
    const node = scrollRef.current
    if (shownThread.current !== threadId) {
      prepend.current = null
      readingAnchor.current = null
      shownThread.current = threadId
      const saved = threadId ? positions.current.get(threadId) : undefined
      atBottom.current = saved?.atBottom ?? true
      if (node) node.scrollTop = atBottom.current ? node.scrollHeight : saved?.top ?? 0
    } else if (node && prepend.current?.threadId === threadId) {
      const anchor = prepend.current
      prepend.current = null
      readingAnchor.current = anchor
      if (node.contains(anchor.element)) alignReadingAnchor(node)
      else {
        readingAnchor.current = null
        node.scrollTop = anchor.top + node.scrollHeight - anchor.height
        atBottom.current = false
        remember()
      }
    } else if (node && atBottom.current) {
      node.scrollTop = node.scrollHeight
    }
  }, [ownerId, threadId, content])

  useLayoutEffect(() => {
    const node = scrollRef.current
    if (!node) return
    const observer = new ResizeObserver(() => {
      if (readingAnchor.current) alignReadingAnchor(node)
      else if (atBottom.current) node.scrollTop = node.scrollHeight
    })
    observer.observe(node)
    if (node.firstElementChild) observer.observe(node.firstElementChild)
    const cancelAnchor = () => { prepend.current = null; readingAnchor.current = null }
    const onScrollKey = (event: KeyboardEvent) => {
      if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key))
        cancelAnchor()
    }
    node.addEventListener('wheel', cancelAnchor, { passive: true })
    node.addEventListener('touchstart', cancelAnchor, { passive: true })
    node.addEventListener('pointerdown', cancelAnchor)
    window.addEventListener('keydown', onScrollKey)
    return () => {
      observer.disconnect()
      node.removeEventListener('wheel', cancelAnchor)
      node.removeEventListener('touchstart', cancelAnchor)
      node.removeEventListener('pointerdown', cancelAnchor)
      window.removeEventListener('keydown', onScrollKey)
    }
  }, [threadId, content.length > 0])

  return { scrollRef, onScroll, remember, preparePrepend }
}
