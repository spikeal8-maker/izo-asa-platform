import { useRef, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import type { components } from '../../shared/api.generated'

export type Price = components['schemas']['Price']
export type Model = components['schemas']['izo__catalog__schemas__ModelView']
export type Catalog = components['schemas']['CatalogView']

export function catalogError(reason: unknown) {
  if (reason instanceof ApiError) {
    if (reason.status === 401) return 'Войдите в серверный аккаунт.'
    if (reason.status === 403) return 'Нет полномочия для каталога.'
    if (reason.code === 'catalog_revision_conflict') return 'Каталог изменился. Обновите данные перед новой правкой.'
    if (reason.code === 'catalog_operation_conflict') return 'Эта операция уже использована с другими данными.'
    if (reason.status === 422) return 'Проверьте параметры модели и цены.'
  }
  return 'Результат неизвестен. Проверьте каталог; повтор с теми же данными сохранит номер операции.'
}

function priceInput(kopeks: number | null | undefined) {
  return kopeks == null ? '' : (kopeks / 100).toFixed(2)
}

function parsePrice(value: string): number | null | undefined {
  const normalized = value.trim().replace(',', '.')
  if (!normalized) return null
  if (!/^\d{1,9}(?:\.\d{1,2})?$/.test(normalized)) return undefined
  const [rubles, fraction = ''] = normalized.split('.')
  return Number(rubles) * 100 + Number(fraction.padEnd(2, '0'))
}

export function AdminCatalogEditor({ model, catalog, auth, onSaved, onCancel }: {
  model: Model
  catalog: Catalog
  auth: AuthView
  onSaved: (value: Catalog) => void
  onCancel: () => void
}) {
  const [published, setPublished] = useState(model.published)
  const [enabled, setEnabled] = useState(model.enabled)
  const [isDefault, setIsDefault] = useState(model.is_default)
  const [input, setInput] = useState(priceInput(model.price.input_kopeks_per_million))
  const [output, setOutput] = useState(priceInput(model.price.output_kopeks_per_million))
  const [image, setImage] = useState(priceInput(model.price.image_kopeks_per_image))
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const operation = useRef({ fingerprint: '', id: '' })
  const canPrice = catalog.permissions.includes('pricing.write')
  const runtimeUnavailable = !model.publishable

  async function save(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const inputAmount = parsePrice(input)
    const outputAmount = parsePrice(output)
    const imageAmount = parsePrice(image)
    if (inputAmount === undefined || outputAmount === undefined || imageAmount === undefined) {
      setError('Укажите сумму в рублях с точностью до копейки или оставьте поле пустым.'); return
    }
    const price: Price = canPrice ? {
      currency: 'RUB', input_kopeks_per_million: model.modality === 'text' ? inputAmount : null,
      output_kopeks_per_million: model.modality === 'text' ? outputAmount : null,
      image_kopeks_per_image: model.modality === 'image' ? imageAmount : null,
    } : model.price
    const command = { expected_revision: catalog.revision, published, enabled,
      is_default: isDefault, price, reason: reason.trim() }
    if (!command.reason) { setError('Укажите причину изменения.'); return }
    const fingerprint = JSON.stringify({ model_id: model.id, ...command })
    if (operation.current.fingerprint !== fingerprint) {
      operation.current = { fingerprint, id: crypto.randomUUID() }
    }
    setBusy(true); setError('')
    try {
      const value = await apiRequest<Catalog>(`/api/v1/admin/catalog/models/${encodeURIComponent(model.id)}`, {
        method: 'PATCH', csrf: auth.csrf_token,
        data: { operation_id: operation.current.id, ...command },
      })
      operation.current = { fingerprint: '', id: '' }
      onSaved(value)
    } catch (problem) { setError(catalogError(problem)) }
    finally { setBusy(false) }
  }

  return <form className="admin-panel admin-form" onSubmit={event => void save(event)}>
    <h2>Настроить: {model.label}</h2>
    {runtimeUnavailable && <p>Эта модель пока доступна только как черновик отображаемой цены.
      Публикация и включение станут доступны после подключения исполнения.</p>}
    <label><input type="checkbox" checked={published} disabled={runtimeUnavailable}
      onChange={event => setPublished(event.target.checked)} /> Опубликована</label>
    <label><input type="checkbox" checked={enabled} disabled={runtimeUnavailable}
      onChange={event => setEnabled(event.target.checked)} /> Включена</label>
    {model.modality === 'text' && <label><input type="checkbox" checked={isDefault}
      onChange={event => setIsDefault(event.target.checked)} /> По умолчанию для чата</label>}
    {model.modality === 'text' ? <>
      <label>Вход, ₽ за 1 млн токенов <input inputMode="decimal" value={input} disabled={!canPrice}
        onChange={event => setInput(event.target.value)} placeholder="Цена не задана" /></label>
      <label>Выход, ₽ за 1 млн токенов <input inputMode="decimal" value={output} disabled={!canPrice}
        onChange={event => setOutput(event.target.value)} placeholder="Цена не задана" /></label>
    </> : <label>Цена, ₽ за изображение <input inputMode="decimal" value={image} disabled={!canPrice}
      onChange={event => setImage(event.target.value)} placeholder="Цена не задана" /></label>}
    {!canPrice && <p>Для изменения цен требуется полномочие pricing.write.</p>}
    <label>Причина изменения <input value={reason} minLength={3} maxLength={200} required
      onChange={event => setReason(event.target.value)} /></label>
    {error && <p role="alert" className="field-error">{error}</p>}
    <div><button type="submit" className="primary" disabled={busy}>Сохранить</button>{' '}
      <button type="button" disabled={busy} onClick={onCancel}>Отмена</button></div>
  </form>
}
