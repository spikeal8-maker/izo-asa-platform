import { useEffect } from 'react'

export function useVisualViewport() {
  useEffect(() => {
    const root = document.documentElement
    const viewport = window.visualViewport
    let baseline = Math.max(window.innerHeight, viewport?.height ?? 0)

    const update = () => {
      const height = viewport?.height ?? window.innerHeight
      const top = viewport?.offsetTop ?? 0
      if (height > baseline - 32) baseline = Math.max(baseline, height)
      root.style.setProperty('--chat-viewport-height', `${Math.round(height)}px`)
      root.style.setProperty('--chat-viewport-top', `${Math.round(top)}px`)
      root.dataset.chatKeyboard = height < baseline - 120 ? 'open' : 'closed'
    }

    update()
    viewport?.addEventListener('resize', update)
    viewport?.addEventListener('scroll', update)
    window.addEventListener('resize', update)
    return () => {
      viewport?.removeEventListener('resize', update)
      viewport?.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
      root.style.removeProperty('--chat-viewport-height')
      root.style.removeProperty('--chat-viewport-top')
      delete root.dataset.chatKeyboard
    }
  }, [])
}
