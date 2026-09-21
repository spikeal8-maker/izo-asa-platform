import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'

export function menuKeyboard(event: KeyboardEvent<HTMLElement>, close: () => void, opener: HTMLElement | null) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    requestAnimationFrame(() => opener?.focus())
    return
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
    '[role="menuitem"]:not([aria-disabled="true"]),[role="menuitemradio"]:not([aria-disabled="true"])',
  )).filter(item => item.offsetParent !== null)
  if (!items.length) return
  event.preventDefault()
  const current = items.indexOf(document.activeElement as HTMLElement)
  let next = current
  if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = items.length - 1
  else if (event.key === 'ArrowDown') next = current < 0 ? 0 : (current + 1) % items.length
  else next = current < 0 ? items.length - 1 : (current - 1 + items.length) % items.length
  items[next]?.focus()
}

function px(value: string) {
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function useComposerLayout(value: string, forcedExpanded: boolean) {
  const formRef = useRef<HTMLFormElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const measureRef = useRef<HTMLDivElement>(null)
  const wrappedRef = useRef(false)
  const [wrapped, setWrapped] = useState(false)

  const updateWrapped = useCallback((next: boolean) => {
    if (wrappedRef.current === next) return
    wrappedRef.current = next
    setWrapped(next)
  }, [])

  const measure = useCallback((allowCollapse: boolean) => {
    const form = formRef.current
    const textarea = textareaRef.current
    const mirror = measureRef.current
    if (!form || !textarea || !mirror) return

    const formStyle = getComputedStyle(form)
    const controls = Array.from(form.querySelectorAll<HTMLElement>('[data-composer-control="compact"]'))
    const controlsWidth = controls.reduce((sum, control) => sum + control.getBoundingClientRect().width, 0)
    const innerWidth = form.clientWidth - px(formStyle.paddingLeft) - px(formStyle.paddingRight)
    const gap = px(formStyle.columnGap)
    const compactWidth = Math.max(48, innerWidth - controlsWidth - gap * controls.length)
    mirror.style.width = `${compactWidth}px`
    mirror.textContent = textarea.value || ' '

    const mirrorStyle = getComputedStyle(mirror)
    const lineHeight = px(mirrorStyle.lineHeight)
    const oneLine = lineHeight + px(mirrorStyle.paddingTop) + px(mirrorStyle.paddingBottom)
    const wraps = textarea.value.includes('\n') || mirror.scrollHeight > oneLine + 1
    const empty = textarea.value.length === 0
    let next = wrappedRef.current
    if (empty) next = false
    else if (wraps) next = true
    else if (allowCollapse) next = false
    updateWrapped(next)

    textarea.style.height = 'auto'
    if (forcedExpanded || next) {
      const maxHeight = px(getComputedStyle(textarea).maxHeight) || 320
      textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`
    } else textarea.style.height = ''
  }, [forcedExpanded, updateWrapped])

  useLayoutEffect(() => measure(true), [value, forcedExpanded, measure])

  useEffect(() => {
    const form = formRef.current
    if (!form) return
    const observer = new ResizeObserver(() => measure(false))
    observer.observe(form)
    return () => observer.disconnect()
  }, [measure])

  return { formRef, textareaRef, measureRef, expanded: forcedExpanded || wrapped }
}
