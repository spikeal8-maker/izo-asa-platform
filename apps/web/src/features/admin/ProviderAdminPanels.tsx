import type { FormEvent, RefObject } from 'react'
import { Link } from '../../shell/router'
import { labels, type Provider } from './provider-admin-types'

export function ProviderAdminHeader() {
  return <>
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
  </>
}

export function ProviderAdminStageNote() {
  return <p className="provider-limit"><strong>Граница этапа B1.</strong> Здесь реально сохраняются, проверяются и выключаются
    настройки подключения. Маршрутизация пользовательских запросов и контроль расходов будут включены отдельным
    проверяемым этапом. В тестовом окружении проверка ключа синтетическая, без обращения к DeepSeek.</p>
}

type Action = 'save' | 'verify' | 'policy'
type Props = {
  provider: Provider
  keyValue: string
  setKey: (text: string) => void
  password: string
  setPassword: (text: string) => void
  passwordInputRef: RefObject<HTMLInputElement | null>
  model: Provider['model']
  setModel: (model: Provider['model']) => void
  enabled: boolean
  setEnabled: (enabled: boolean) => void
  daily: number
  setDaily: (count: number) => void
  concurrency: number
  setConcurrency: (count: number) => void
  busy: boolean
  change: (kind: Action) => Promise<void>
  form: (event: FormEvent, kind: Action) => void
}

export function ProviderAdminPanels(props: Props) {
  const { provider, keyValue: key, setKey, password, setPassword, passwordInputRef,
    model, setModel, enabled, setEnabled, daily, setDaily,
    concurrency, setConcurrency, busy, change, form } = props
  return <>
    <section className="provider-auth provider-auth-top" aria-labelledby="provider-auth-title">
      <div className="provider-auth-intro">
        <h2 id="provider-auth-title">Подтверждение действий</h2>
        <p>Чтобы сохранить ключ, проверить подключение или изменить лимиты, введите пароль, с которым вы входите в IZO ASA. Это не API-ключ.</p>
      </div>
      <div className="provider-auth-control">
        <label htmlFor="provider-admin-password">Текущий пароль аккаунта IZO ASA</label>
        <input id="provider-admin-password" ref={passwordInputRef} type="password" autoComplete="current-password"
          value={password} onChange={e => setPassword(e.target.value)} minLength={1} maxLength={128} />
        <p>Пароль нужен для каждой операции, очищается после попытки и не сохраняется в браузере.</p>
      </div>
    </section>
    <div className="provider-columns">
      <div className="admin-panel provider-panel">
        <div className="provider-heading">
          <div><small>ПОДКЛЮЧЕНИЕ</small><h2>DeepSeek</h2></div>
          <strong>{labels[provider.status]}</strong>
        </div>
        <dl className="summary-list">
          <div><dt>Ключ</dt><dd>{provider.configured ? 'Сохранён на сервере' : 'Не добавлен'}</dd></div>
          <div><dt>Проверка</dt><dd>{provider.verified ? 'Выполнена' : 'Не выполнена'}</dd></div>
          <div><dt>Версия настроек</dt><dd>{provider.revision ?? '—'}</dd></div>
          <div><dt>Пользователям</dt><dd>{provider.available_to_users ? 'Доступен' : 'Ещё не подключён'}</dd></div>
        </dl>
        <form onSubmit={event => form(event, 'save')} className="provider-form">
          <h3>Добавить или заменить ключ</h3>
          <label>Новый API-ключ
            <input type="password" autoComplete="off" spellCheck={false}
              value={key} onChange={e => setKey(e.target.value)}
              minLength={8} maxLength={512} required />
          </label>
          <button className="primary" type="submit" disabled={busy || !key.trim()}>
            Сохранить ключ на сервере
          </button>
        </form>
        <button type="button" disabled={!provider.configured || busy}
          onClick={() => void change('verify')}>Проверить подключение</button>
        {!provider.configured && <p className="provider-action-hint">Проверка станет доступна после сохранения API-ключа.</p>}
      </div>
      <div className="admin-panel provider-panel">
        <h2>Модель и ограничения</h2>
        <form onSubmit={event => form(event, 'policy')} className="provider-form">
          <label>Модель
            <select value={model} onChange={e => setModel(e.target.value as Provider['model'])}>
              <option value="deepseek-flash">DeepSeek Flash</option>
              <option value="deepseek-v4-pro">DeepSeek V4 Pro</option>
            </select>
          </label>
          <label>Лимит запросов в сутки
            <input type="number" min={1} max={200} step={1} value={daily}
              onChange={e => setDaily(Number(e.target.value))} required />
          </label>
          <label>Максимум одновременных запросов
            <input type="number" min={1} max={10} step={1} value={concurrency}
              onChange={e => setConcurrency(Number(e.target.value))} required />
          </label>
          <label className="provider-check"><input type="checkbox" checked={enabled}
            onChange={e => setEnabled(e.target.checked)} /> Разрешить подключение в настройках</label>
          <button className="primary" type="submit" disabled={busy || !provider.configured}>
            Сохранить настройки
          </button>
        </form>
      </div>
    </div>
  </>
}
