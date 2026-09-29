import { useEffect, useState, type ComponentProps } from 'react'

export function usePath() {
  const [path, setPath] = useState(() => window.location.pathname.replace(/\/$/, '') || '/')
  useEffect(() => {
    const update = () => setPath(window.location.pathname.replace(/\/$/, '') || '/')
    window.addEventListener('popstate', update)
    window.addEventListener('izo:navigate', update)
    return () => { window.removeEventListener('popstate', update); window.removeEventListener('izo:navigate', update) }
  }, [])
  return path
}
export function Link({ href, onClick, ...props }: ComponentProps<'a'>) {
  return <a {...props} href={href} onClick={event => {
    onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || props.target || props.download || !href?.startsWith('/') || href.startsWith('//')) return
    event.preventDefault()
    window.history.pushState(null, '', href)
    window.dispatchEvent(new Event('izo:navigate'))
    window.scrollTo({ top: 0 })
  }} />
}
