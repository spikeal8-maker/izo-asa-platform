import { useEffect, useState, type ReactNode } from 'react'
import { apiRequest, ApiError, type AuthView } from './api'
import { problem } from './workspace-api'
import { Link } from '../shell/router'

/** The backend owns permissions. This boundary prevents stale private UI across sessions. */
export function WorkspaceGate({ children }: { children: (auth: AuthView) => ReactNode }) {
  const [auth, setAuth] = useState<AuthView | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setAuth(null)
    apiRequest<AuthView>('/api/v1/auth/me', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setAuth(value)
    }).catch(reason => {
      if (!controller.signal.aborted && !(reason instanceof ApiError && reason.status === 401)) setError(problem(reason))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [version])
  useEffect(() => {
    const invalid = () => { setAuth(null); setLoading(false); setError('') }
    const visible = () => { if (document.visibilityState === 'visible') setVersion(v => v + 1) }
    window.addEventListener('izo:session-invalid', invalid)
    window.addEventListener('focus', visible)
    document.addEventListener('visibilitychange', visible)
    return () => {
      window.removeEventListener('izo:session-invalid', invalid)
      window.removeEventListener('focus', visible)
      document.removeEventListener('visibilitychange', visible)
    }
  }, [])
  if (loading) return <p role="status">Проверяем серверную сессию…</p>
  if (error) return <div role="alert" className="field-error">{error}
    <button onClick={() => setVersion(v => v + 1)}>Повторить проверку сессии</button></div>
  if (!auth) return <section className="gallery-empty"><h2>Войдите, чтобы продолжить</h2>
    <p>Работы и баллы доступны только владельцу. Демо-данные не подставляются.</p>
    <Link className="primary" href="/login">Войти</Link></section>
  return <div key={auth.account.id} data-testid="server-workspace">{children(auth)}</div>
}

/** Sequential polling; abort old routes, stop on errors and terminal states. */
export function useResource<T>(path: string, poll?: (value: T) => boolean) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    setData(null); setLoading(true); setError('')
    async function load() {
      try {
        const value = await apiRequest<T>(path, { signal: controller.signal })
        if (controller.signal.aborted) return
        setData(value); setError('')
        if (poll?.(value)) timer = setTimeout(() => { void load() }, 2000)
      } catch (reason) {
        if (!controller.signal.aborted) { setData(null); setError(problem(reason)) }
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [path, version, poll])
  return { data, error, loading, refresh: () => setVersion(v => v + 1) }
}
export function ResourceState({ error, loading, retry }: { error: string; loading: boolean; retry: () => void }) {
  return <>{loading && <p role="status">Получаем данные…</p>}{error && <div className="field-error" role="alert">
    {error}<button onClick={retry}>Повторить загрузку</button></div>}</>
}
