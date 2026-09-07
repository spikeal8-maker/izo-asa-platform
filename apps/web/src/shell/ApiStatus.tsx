import { useEffect, useState } from 'react'
import { getFoundation } from '../shared/api'

export function ApiStatus() {
  const [state, setState] = useState<'loading' | 'ready' | 'offline'>('loading')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    getFoundation(controller.signal).then(() => setState('ready')).catch(() => {
      if (!controller.signal.aborted) setState('offline')
    })
    return () => controller.abort()
  }, [attempt])
  return <div className="api-status" role="status">
    <span className={`status-dot ${state}`} aria-hidden="true" />
    {state === 'loading' ? 'Подключение к API' : state === 'ready' ? 'API отвечает' : 'API недоступен'}
    {state === 'offline' && <button onClick={() => { setState('loading'); setAttempt(v => v + 1) }}>Повторить</button>}
  </div>
}
