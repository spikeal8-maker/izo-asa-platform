import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, apiRequest, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import './provider-admin.css'
import { ProviderAdminPanels } from './ProviderAdminPanels'

import { endpoint, explainProviderError as explain, type Provider, type ProviderList } from './provider-admin-types'

const requestId = () => crypto.randomUUID()
type Kind = 'save' | 'verify' | 'policy'
type Pending = { kind: Kind; payload: Record<string, unknown> }

export function ProviderAdminPage({ auth }: { auth: AuthView | null | undefined }) {
  const [provider, setProvider] = useState<Provider | null>(null)
  const [key, setKey] = useState('')
  const [password, setPassword] = useState('')
  const passwordInputRef = useRef<HTMLInputElement>(null)
  const [model, setModel] = useState<Provider['model']>('deepseek-flash')
  const [enabled, setEnabled] = useState(false)
  const [daily, setDaily] = useState(30)
  const [concurrency, setConcurrency] = useState(1)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [uncertain, setUncertain] = useState(false)
  const [sessionInvalid, setSessionInvalid] = useState(false)
  // Volatile secrets and original UUID are discarded on session invalidation/unmount.
  const pending = useRef<Pending | null>(null)
  const invalidated = useRef(false)
  useEffect(() => {
    const clearPrivateState = () => {
      invalidated.current = true
      pending.current = null
      setSessionInvalid(true); setProvider(null)
      setKey(''); setPassword(''); setUncertain(false); setBusy(false)
      setNotice(''); setError('Сессия завершилась. Войдите повторно.')
    }
    window.addEventListener('izo:session-invalid', clearPrivateState)
    return () => {
      window.removeEventListener('izo:session-invalid', clearPrivateState)
      pending.current = null
    }
  }, [])

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const result = await apiRequest<ProviderList>(endpoint, { signal })
    const item = result.connections[0]
    if (!item) throw Error('Missing configured provider')
    if (invalidated.current || signal?.aborted) return
    setProvider(item)
    setModel(item.model); setEnabled(item.enabled)
    setDaily(item.daily_limit); setConcurrency(item.concurrency_limit)
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void refresh(controller.signal).catch(e => {
      if (!controller.signal.aborted && !invalidated.current) setError(explain(e))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [refresh])

  async function change(kind: Kind) {
    if (!provider || busy || !auth || invalidated.current) return
    if (!password && !pending.current) {
      setNotice('')
      setError('Для сохранения ключа, проверки подключения и изменения настроек введите текущий пароль вашего аккаунта IZO ASA в поле «Подтверждение действий» над карточками.')
      passwordInputRef.current?.focus()
      return
    }
    if (kind !== 'save' && provider.revision === null && !pending.current) return
    if (pending.current && pending.current.kind !== kind) return
    const retryingPending = pending.current !== null
    setBusy(true); setError(''); setNotice('')
    const body = { operation_id: requestId(), current_password: password }
    const operation = pending.current ?? {
      kind, payload: kind === 'save'
        ? { ...body, key, expected_revision: provider.revision }
        : kind === 'verify' ? { ...body, expected_revision: provider.revision }
          : { ...body, expected_revision: provider.revision, enabled,
            model, daily_limit: daily, concurrency_limit: concurrency },
    }
    pending.current = operation
    try {
      const route = kind === 'save' ? '/deepseek/credential'
        : kind === 'verify' ? '/deepseek/verify' : '/deepseek/config'
      const updated = await apiRequest<Provider>(endpoint + route, {
        method: kind === 'policy' ? 'PATCH' : 'POST',
        csrf: auth.csrf_token, data: operation.payload,
      })
      pending.current = null; setUncertain(false)
      setPassword('')
      if (kind === 'save') setKey('')
      setProvider(updated); setEnabled(updated.enabled); setModel(updated.model)
      setDaily(updated.daily_limit); setConcurrency(updated.concurrency_limit)
      setNotice(kind === 'save' ? 'Новый ключ зашифрован на сервере. Требуется проверка.'
        : kind === 'verify' ? 'Сервер подтвердил проверку выбранным адаптером.'
          : 'Настройки сохранены в PostgreSQL.')
    } catch (reason) {
      if (invalidated.current) return
      const throttledReplay = retryingPending && reason instanceof ApiError && reason.status === 429
      if (!(reason instanceof ApiError) || reason.status >= 500 || throttledReplay) {
        // A throttled replay is not evidence the earlier uncertain write failed:
        // throttle runs before the server checks the original operation UUID.
        setUncertain(true)
        setError(throttledReplay
          ? 'Повтор временно ограничен. Исходный UUID сохранён; новые изменения заблокированы до повтора или успешной сверки.'
          : 'Ответ сервера неизвестен. Повторите ту же операцию или явно сбросьте её после проверки состояния.')
      } else {
        pending.current = null; setUncertain(false); setPassword('')
        setError(explain(reason))
      }
    } finally { setBusy(false) }
  }

  function form(event: FormEvent, kind: Kind) {
    event.preventDefault(); void change(kind)
  }
  async function abandonPending() {
    if (!pending.current || busy || invalidated.current) return
    setBusy(true); setLoading(true); setError('')
    try {
      await refresh()
      if (invalidated.current) return
      // A successful server read, not an attempted read, releases the old UUID.
      pending.current = null; setUncertain(false)
      setKey(''); setPassword('')
      setNotice('Состояние сервера обновлено. Проверьте результат перед новой операцией.')
    } catch (reason) {
      if (!invalidated.current) setError(explain(reason))
      // A failed GET keeps the original UUID/payload and all mutations locked.
    } finally { setLoading(false); setBusy(false) }
  }
  return <section className="admin-page provider-admin">
    <header className="page-heading">
      <p className="eyebrow">АДМИНИСТРИРОВАНИЕ / ИИ</p>
      <h1>Провайдеры</h1>
      <p>Защищённые серверные подключения. Личные ключи пользователей остаются отдельным BYOK-режимом.</p>
    </header>
    <nav className="admin-links" aria-label="Административные разделы">
      <Link href="/admin/users">Пользователи</Link>
      <Link href="/admin/catalog">Каталог моделей</Link>
      <Link href="/admin/access">Доступ</Link>
      <Link href="/admin/audit">Аудит</Link>
      <Link href="/admin/providers" aria-current="page">Провайдеры</Link>
    </nav>
    {loading && <p role="status">Загружаем настройки подключения…</p>}
    {error && <p className="field-error" role="alert">{error}</p>}
    {notice && <p role="status" className="provider-notice">{notice}</p>}
    {uncertain && <div className="provider-notice" role="group" aria-label="Неопределённая операция">
      <p>Запрос мог выполниться. Повтор использует сохранённые только в памяти UUID и данные.</p>
      <button type="button" disabled={busy} onClick={() => {
        if (pending.current) void change(pending.current.kind)
      }}>Повторить исходную операцию</button>
      <button type="button" disabled={busy} onClick={abandonPending}>Отказаться от повтора и перечитать состояние</button>
    </div>}
    {!loading && !sessionInvalid && <button type="button" onClick={() => {
      setError(''); setNotice(''); setLoading(true)
      void refresh().catch(e => { if (!invalidated.current) setError(explain(e)) })
        .finally(() => setLoading(false))
    }} disabled={busy || uncertain}>Обновить состояние</button>}
    {!sessionInvalid && provider && <ProviderAdminPanels provider={provider}
      keyValue={key} setKey={setKey}
      password={password} setPassword={text => { setPassword(text); if (error) setError('') }}
      passwordInputRef={passwordInputRef}
      model={model} setModel={setModel}
      enabled={enabled} setEnabled={setEnabled}
      daily={daily} setDaily={setDaily}
      concurrency={concurrency} setConcurrency={setConcurrency}
      busy={busy || uncertain} change={change} form={form} />}
    <p className="provider-limit"><strong>Граница этапа B1.</strong> Здесь реально сохраняются, проверяются и выключаются
      настройки подключения. Маршрутизация пользовательских запросов и контроль расходов будут включены отдельным
      проверяемым этапом. В тестовом окружении проверка ключа синтетическая, без обращения к DeepSeek.</p>
  </section>
}
