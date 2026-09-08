import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Icon } from './Icon'

export function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  const label = useId()
  useEffect(() => {
    const element = ref.current
    if (!element || !open) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    element.showModal()
    return () => {
      element.close()
      if (previous?.isConnected) previous.focus()
    }
  }, [open])
  return <dialog ref={ref} className="ui-dialog" aria-labelledby={label} onCancel={onClose}>
    <div className="dialog-heading"><h2 id={label}>{title}</h2><button type="button" className="icon-button" aria-label="Закрыть диалог" onClick={onClose} autoFocus><Icon name="close" /></button></div>
    {children}
  </dialog>
}
