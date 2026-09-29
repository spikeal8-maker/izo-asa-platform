import { useEffect, useState } from 'react'
import { apiRequest, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { AdminCatalogEditor, catalogError, type Catalog, type Model } from './AdminCatalogEditor'
import '../../shared/ui/records.css'

function amount(kopeks: number | null | undefined, unit: string) {
  if (kopeks == null) return 'Цена не задана'
  if (kopeks === 0) return `0 ₽ / ${unit}`
  return `${(kopeks / 100).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽ / ${unit}`
}

function modelStatus(model: Model) {
  return `${model.published ? model.enabled ? 'Доступна' : 'Отключена' : 'Черновик'}${model.is_default ? ' · по умолчанию' : ''}`
}

function ModelPrice({ model }: { model: Model }) {
  return model.modality === 'text' ? <>
    <div>Вход: {amount(model.price.input_kopeks_per_million, '1 млн токенов')}</div>
    <div>Выход: {amount(model.price.output_kopeks_per_million, '1 млн токенов')}</div>
  </> : <div>{amount(model.price.image_kopeks_per_image, 'изображение')}</div>
}

export function AdminCatalogPage({ auth }: { auth: AuthView | null | undefined }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!auth) { setBusy(false); setCatalog(null); return }
    const controller = new AbortController()
    setBusy(true); setError(''); setCatalog(null)
    apiRequest<Catalog>('/api/v1/admin/catalog', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setCatalog(value) })
      .catch(reason => { if (!controller.signal.aborted) setError(catalogError(reason)) })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [auth?.account.id, reload])

  const selected = catalog?.models.find(model => model.id === selectedId)
  const canWrite = catalog?.permissions.includes('catalog.write') ?? false
  return <section className="admin-page admin-catalog-page">
    <header className="page-heading"><p className="eyebrow">АДМИНИСТРИРОВАНИЕ</p>
      <h1>Каталог моделей</h1>
      <p>Публикация моделей и отображаемые цены в рублях. Списание с Credits пока не подключено.</p></header>
    <nav className="admin-links" aria-label="Административные страницы">
      <Link href="/admin/catalog" aria-current="page">Модели</Link>
      {auth?.account.permissions.includes('users.read_limited') && <Link href="/admin/users">Пользователи</Link>}
      {auth?.account.permissions.includes('access.read') && <Link href="/admin/access">Доступ</Link>}
    </nav>
    {auth === undefined ? <p role="status">Проверяем вход…</p>
      : auth === null ? <p><Link href="/login">Войти</Link>, чтобы открыть каталог.</p>
        : <>
          {busy && <p role="status">Загружаем каталог…</p>}
          {error && <p role="alert" className="field-error">{error} <button type="button"
            onClick={() => setReload(value => value + 1)} disabled={busy}>Обновить каталог</button></p>}
          {catalog && <>
            <p>Версия каталога: {catalog.revision}</p>
            <div className="admin-panel admin-panel-flat">
              <div className="admin-section-heading"><h2>Провайдеры</h2></div>
              <p>{catalog.providers.map(provider => provider.label).join(' · ') || 'Провайдеры не опубликованы'}</p>
            </div>
            <div className="admin-panel admin-panel-flat">
              <div className="admin-section-heading"><h2>Модели</h2></div>
              <div className="admin-table-wrap admin-catalog-table"><table><thead><tr>
                <th>Модель</th><th>Провайдер</th><th>Состояние</th><th>Отображаемая цена</th>{canWrite && <th>Действие</th>}
              </tr></thead><tbody>{catalog.models.map(model => <tr key={model.id}>
                <td><strong>{model.label}</strong><br /><small>{model.id}</small></td>
                <td>{catalog.providers.find(provider => provider.id === model.provider)?.label ?? model.provider}</td>
                <td>{modelStatus(model)}</td>
                <td><ModelPrice model={model} /></td>
                {canWrite && <td><button type="button" onClick={() => setSelectedId(model.id)}>
                  Настроить</button></td>}
              </tr>)}</tbody></table></div>
              <div className="admin-catalog-cards">{catalog.models.map(model => <article className="admin-catalog-card" key={model.id}>
                <h3>{model.label}</h3><small>{model.id}</small>
                <dl><div><dt>Провайдер</dt><dd>{catalog.providers.find(provider => provider.id === model.provider)?.label ?? model.provider}</dd></div>
                  <div><dt>Состояние</dt><dd>{modelStatus(model)}</dd></div>
                  <div><dt>Отображаемая цена</dt><dd><ModelPrice model={model} /></dd></div></dl>
                {canWrite && <button type="button" onClick={() => setSelectedId(model.id)}>Настроить</button>}
              </article>)}</div>
              {!catalog.models.length && <p>Моделей пока нет.</p>}
            </div>
            {selected && canWrite && <AdminCatalogEditor key={`${selected.id}:${catalog.revision}`}
              model={selected} catalog={catalog} auth={auth} onSaved={value => {
                setCatalog(value); setSelectedId(null); setError('')
              }} onCancel={() => setSelectedId(null)} />}
          </>}
        </>}
  </section>
}
