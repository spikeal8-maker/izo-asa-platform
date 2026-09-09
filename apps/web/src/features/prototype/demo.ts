export const DEMO_KEY = 'izo-ux001-demo-v1'
export const models = [
  { id: 'api-demo', title: 'Studio · API', description: 'Макет внешней модели. Никаких API-вызовов.', cost: 8, enabled: true },
  { id: 'local-demo', title: 'Studio · Local', description: 'Макет локальной модели. GPU не подключён.', cost: 4, enabled: true },
  { id: 'future-demo', title: 'Следующая модель', description: 'Пока недоступна', cost: 0, enabled: false },
] as const
export type Aspect = '1:1' | '4:3' | '16:9' | '9:16'
export const aspects: Aspect[] = ['1:1', '4:3', '16:9', '9:16']
export type Draft = { prompt: string; model: string; aspect: Aspect; palette: number }
export type Work = Draft & { id: string; createdAt: number; title: string }
export type Job = Draft & { id: string; startedAt: number; cost: number; state: 'running' | 'succeeded' | 'failed' | 'cancelled'; fail: boolean }
export type DemoState = { version: 1; draft: Draft; balance: number; works: Work[]; job: Job | null }
export function freshState(): DemoState {
  return { version: 1, draft: { prompt: '', model: 'api-demo', aspect: '1:1', palette: 0 }, balance: 48, works: [], job: null }
}
function validDraft(value: unknown): value is Draft {
  if (!value || typeof value !== 'object') return false
  const d = value as Draft
  return typeof d.prompt === 'string' && d.prompt.length <= 1500 && models.some(m => m.id === d.model && m.enabled)
    && aspects.includes(d.aspect) && Number.isInteger(d.palette) && d.palette >= 0 && d.palette < 4
}
export function restoreDemo(raw: string | null): DemoState {
  try {
    if (!raw || raw.length > 100000) return freshState()
    const d = JSON.parse(raw) as DemoState
    if (d.version !== 1 || !validDraft(d.draft) || !Number.isInteger(d.balance) || d.balance < 0 || d.balance > 48 || !Array.isArray(d.works) || d.works.length > 24) return freshState()
    if (d.works.some(w => !validDraft(w) || typeof w.id !== 'string' || !/^demo-[a-f0-9-]{36}$/.test(w.id) || typeof w.title !== 'string' || w.title.length > 80 || !Number.isFinite(w.createdAt))) return freshState()
    if (d.job) {
      const j = d.job
      const model = models.find(m => m.id === j.model && m.enabled)
      if (!validDraft(j) || !/^demo-[a-f0-9-]{36}$/.test(j.id) || !Number.isFinite(j.startedAt) || typeof j.fail !== 'boolean' || !['running', 'succeeded', 'failed', 'cancelled'].includes(j.state) || j.cost !== model?.cost || (j.state === 'running' && j.cost > d.balance)) return freshState()
    }
    return d
  } catch { return freshState() }
}
export function settleDemo(state: DemoState, now: number): DemoState {
  const job = state.job
  if (!job || job.state !== 'running' || now - job.startedAt < 1400) return state
  if (job.fail) return { ...state, job: { ...job, state: 'failed' } }
  const work: Work = { id: job.id, prompt: job.prompt, model: job.model, aspect: job.aspect, palette: job.palette, title: job.prompt.slice(0, 65), createdAt: now }
  return { ...state, balance: state.balance - job.cost, job: { ...job, state: 'succeeded' }, works: [work, ...state.works.filter(w => w.id !== job.id)].slice(0, 24) }
}
