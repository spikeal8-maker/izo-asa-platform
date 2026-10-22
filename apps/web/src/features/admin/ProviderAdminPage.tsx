import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ApiError, apiRequest, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import './provider-admin.css'
import { ProviderAdminPanels } from './ProviderAdminPanels'

import { endpoint, type Provider, type ProviderList } from './provider-admin-types'

function explain(reason: unknown): string {
  if (reason instanceof ApiError) {
    const errors: Record<string, string> = {
      forbidden: 'Недостаточно полномочий для операции.',
      verification_required: 'Подтвердите административную учётную запись.',
      reauth_required: 'Неверный текущий пароль администратора.',
      provider_not_verified: 'Сначала проверьте подключение.',
      provider_not_configured: 'Сначала сохраните ключ.',
      provider_revision_conflict: 'Настройки изменились. Обновите данные.',
      provider_changed_during_verify: 'Ключ изменился во время проверки. Повторите чтение.',
      credential_rejected: 'Проверка отклонила ключ. Подключение не подтверждено.',
      credential_unavailable: 'Не удалось прочитать зашифрованный ключ.',
      credential_storage_unavailable: 'На сервере недоступен корневой ключ шифрования.',
      rate_limited: 'Достигнут лимит проверок. Повторите позже.',
      invalid_input: 'Проверьте поля и ограничения.'
    }
    return errors[reason.code] ?? 'Сервер отклонил операцию (' + reason.code + ').'
  }
  return 'Нет ответа от сервера. Обновите данные перед повтором.'
}
const requestId = () => crypto.randomUUID()

export function ProviderAdminPage({ auth }: { auth: AuthView | null | undefined }) {
  const [provider, setProvider] = useState<Provider | null>(null)
  const [key, setKey] = useState('')
  const [password, setPassword] = useState('')
  const [model, setModel] = useState<Provider['model']>('deepseek-flash')
  const [enabled, setEnabled] = useState(false)
  const [daily, setDaily] = useState(30)
  const [concurrency, setConcurrency] = useState(1)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const result = await apiRequest<ProviderList>(endpoint, { signal })
    const item = result.connections[0]
    if (!item) throw Error('Missing configured provider')
    setProvider(item)
    setModel(item.model); setEnabled(item.enabled)
    setDaily(item.daily_limit); setConcurrency(item.concurrency_limit)
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void refresh(controller.signal).catch(e => {
      if (!controller.signal.aborted) setError(explain(e))
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [refresh])

  async function change(kind: 'save' | 'verify' | 'policy') {
    if (!provider || busy || !password || !auth) return
    setBusy(true); setError(''); setNotice('')
    try {
      const body = { operation_id: requestId(), current_password: password }
      let updated: Provider
      if (kind === 'save') {
        updated = await apiRequest<Provider>(endpoint + '/deepseek/credential', {
          method: 'POST', csrf: auth.csrf_token,
          data: { ...body, key, expected_revision: provider.revision }
        })
        setKey('')
      } else if (kind === 'verify') {
        if (provider.revision === null) return
        updated = await apiRequest<Provider>(endpoint + '/deepseek/verify', {
          method: 'POST', csrf: auth.csrf_token,
          data: { ...body, expected_revision: provider.revision }
        })
      } else {
        if (provider.revision === null) return
        updated = await apiRequest<Provider>(endpoint + '/deepseek/config', {
          method: 'PATCH', csrf: auth.csrf_token, data: {
            ...body, expected_revision: provider.revision, enabled,
            model, daily_limit: daily, concurrency_limit: concurrency
          }
        })
      }
      setProvider(updated); setEnabled(updated.enabled); setModel(updated.model)
      setDaily(updated.daily_limit); setConcurrency(updated.concurrency_limit)
      setNotice(kind === 'save' ? 'Новый ключ зашифрован на сервере. Требуется проверка.'
        : kind === 'verify' ? 'Сервер подтвердил проверку выбранным адаптером.'
          : 'Настройки сохранены в PostgreSQL.')
    } catch (reason) { setError(explain(reason)) }
    finally { setPassword(''); setBusy(false) }
  }

  function form(event: FormEvent, kind: 'save' | 'verify' | 'policy') {
    event.preventDefault(); void change(kind)
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
    {!loading && <button type="button" onClick={() => {
      setError(''); setNotice(''); setLoading(true)
      void refresh().catch(e => setError(explain(e))).finally(() => setLoading(false))
    }} disabled={busy}>Обновить состояние</button>}
    {provider && <ProviderAdminPanels provider={provider}
      keyValue={key} setKey={setKey}
      password={password} setPassword={setPassword}
      model={model} setModel={setModel}
      enabled={enabled} setEnabled={setEnabled}
      daily={daily} setDaily={setDaily}
      concurrency={concurrency} setConcurrency={setConcurrency}
      busy={busy} change={change} form={form} />}
    <p className="provider-limit"><strong>Граница этапа B1.</strong> Здесь реально сохраняются, проверяются и выключаются
      настройки подключения. Маршрутизация пользовательских запросов и контроль расходов будут включены отдельным
      проверяемым этапом. В тестовом окружении проверка ключа синтетическая, без обращения к DeepSeek.</p>
  </section>
}
