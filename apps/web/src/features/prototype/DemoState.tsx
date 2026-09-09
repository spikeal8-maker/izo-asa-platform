import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { DEMO_KEY, freshState, models, restoreDemo, settleDemo, type DemoState, type Draft } from './demo'

type DemoContext = {
  state: DemoState; storageAvailable: boolean; updateDraft: (draft: Partial<Draft>) => void;
  start: (fail: boolean) => boolean; cancel: () => void; remove: (id: string) => void;
  reset: () => void; setEmptyBalance: (empty: boolean) => void;
}
const Context = createContext<DemoContext | null>(null)

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(() => {
    try { return restoreDemo(sessionStorage.getItem(DEMO_KEY)) } catch { return freshState() }
  })
  const current = useRef(state)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const commit = (next: DemoState) => { current.current = next; setState(next) }
  useEffect(() => {
    try { sessionStorage.setItem(DEMO_KEY, JSON.stringify(state)); setStorageAvailable(true) }
    catch { setStorageAvailable(false) }
  }, [state])
  useEffect(() => {
    if (state.job?.state !== 'running') return
    const timer = window.setInterval(() => {
      const before = current.current
      const after = settleDemo(before, Date.now())
      if (before !== after) commit(after)
    }, 150)
    return () => window.clearInterval(timer)
  }, [state.job?.id, state.job?.state])
  function start(fail: boolean) {
    const before = current.current
    const model = models.find(m => m.id === before.draft.model && m.enabled)
    if (!model || !before.draft.prompt.trim() || before.job?.state === 'running' || before.balance < model.cost || before.works.length >= 24) return false
    const job = { ...before.draft, prompt: before.draft.prompt.trim(), id: `demo-${crypto.randomUUID()}`, startedAt: Date.now(), cost: model.cost, state: 'running' as const, fail }
    commit({ ...before, job })
    return true
  }
  return <Context.Provider value={{ state, storageAvailable, start,
    updateDraft: draft => commit({ ...current.current, draft: { ...current.current.draft, ...draft } }),
    cancel: () => { const s = current.current; if (s.job?.state === 'running') commit({ ...s, job: { ...s.job, state: 'cancelled' } }) },
    remove: id => commit({ ...current.current, works: current.current.works.filter(w => w.id !== id) }),
    reset: () => commit(freshState()),
    setEmptyBalance: empty => { if (current.current.job?.state !== 'running') commit({ ...current.current, balance: empty ? 0 : 48 }) },
  }}>{children}</Context.Provider>
}
export function useDemo() {
  const context = useContext(Context)
  if (!context) throw new Error('DemoProvider required')
  return context
}
