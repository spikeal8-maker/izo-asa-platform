import { useEffect, useState, type RefObject } from 'react'
import type { CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import { menuKeyboard } from './composerLayout'
import {
  autoModel, groupedTextModels, modelAvailable, modelMeta, modelSearchText,
  type ChatModel,
} from './modelCatalog'

function rubles(kopeks: number | null | undefined) {
  if (kopeks == null) return 'Цена не задана'
  if (kopeks === 0) return '0 ₽'
  return `${(kopeks / 100).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`
}
function displayPrice(model: ChatModel) {
  return `Вход ${rubles(model.price?.input_kopeks_per_million)} · выход ${rubles(model.price?.output_kopeks_per_million)} за 1 млн токенов`
}
function favoritesKey(accountId?: string) { return accountId ? `izo-chat-model-favorites:${accountId}` : '' }
function readFavorites(accountId?: string): string[] {
  if (!accountId) return []
  try {
    const value = JSON.parse(localStorage.getItem(favoritesKey(accountId)) ?? '[]')
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
  } catch { return [] }
}

export function ModelPicker({ open, model, models, credentials, accountId, catalogError,
  defaultModelId, busy, buttonRef, onToggle, onClose, onSelect }: {
  open: boolean
  model: ChatModel
  models: ChatModel[]
  credentials: CredentialView[]
  accountId?: string
  catalogError: string
  defaultModelId: string | undefined
  busy: boolean
  buttonRef: RefObject<HTMLButtonElement | null>
  onToggle: () => void
  onClose: () => void
  onSelect: (value: ChatModel) => void
}) {
  const [query, setQuery] = useState('')
  const [favorites, setFavorites] = useState<string[]>(() => readFavorites(accountId))
  useEffect(() => setFavorites(readFavorites(accountId)), [accountId])
  useEffect(() => { if (!open) setQuery('') }, [open])
  const normalized = query.trim().toLocaleLowerCase('ru')
  const visible = models.filter(item => !normalized || modelSearchText(item).includes(normalized))
  const defaultModel = models.find(item => item.id === defaultModelId)
  const defaultAvailable = defaultModel && modelAvailable(defaultModel, credentials)
  function toggleFavorite(id: string) {
    const next = favorites.includes(id) ? favorites.filter(item => item !== id) : [...favorites, id]
    setFavorites(next)
    if (accountId) try { localStorage.setItem(favoritesKey(accountId), JSON.stringify(next)) } catch { /* UI preference only. */ }
  }
  return <>
    <button ref={buttonRef} type="button" className="chat-model-selector"
      data-composer-control="compact" aria-label="Выбрать модель" aria-expanded={open}
      disabled={busy} onClick={onToggle}>
      <span>{model.label}</span><Icon name="chevron" />
    </button>
    {open && <div className="chat-popover chat-model-menu" role="menu" aria-label="Модели"
      onKeyDown={event => menuKeyboard(event, onClose, buttonRef.current)}>
      <label className="chat-model-search"><Icon name="search" />
        <input value={query} onChange={event => setQuery(event.target.value)}
          placeholder="Поиск модели" aria-label="Поиск модели" />
      </label>
      <button type="button" className={model.id === 'auto' ? 'selected model-auto' : 'model-auto'}
        role="menuitemradio" aria-checked={model.id === 'auto'}
        aria-disabled={!defaultAvailable} disabled={!defaultAvailable}
        onClick={() => onSelect(autoModel)}>
        <span>Авто{defaultModel && ` · ${defaultModel.label}`}<br />
          <small>Отображаемая цена: {defaultModel ? displayPrice(defaultModel) : 'Цена не задана'}</small></span>
        {model.id === 'auto' && <Icon name="check" />}
      </button>
      <details className="chat-model-category">
        <summary role="menuitem" tabIndex={0}><span><Icon name="chat" />Текст</span>
          <span>{visible.length}</span></summary>
        <div className="chat-model-category-list">
          {groupedTextModels(visible).map(group =>
            <section className="chat-model-provider" key={group.provider} aria-label={group.label}>
              <div className="chat-model-provider-title">{group.label}</div>
              {group.models.map(item => {
                const available = modelAvailable(item, credentials) && !item.catalog_stale
                return <div className="chat-model-row" key={item.id}>
                  <button type="button" role="menuitemradio"
                    aria-checked={model.id === item.id} aria-disabled={!available}
                    disabled={!available} className={model.id === item.id ? 'selected' : ''}
                    onClick={() => onSelect(item)}>
                    <span className="chat-model-option">
                      <strong>{item.label}</strong>
                      <small>{modelMeta(item)}</small>
                      {item.description && <small>{item.description}</small>}
                      <small>Отображаемая цена: {displayPrice(item)}</small>
                      {item.catalog_dynamic && <small>Тариф OpenRouter проверяйте у провайдера.</small>}
                      {!available && <small>{item.catalog_stale ? 'Каталог устарел' : `Подключите ${group.label} API key`}</small>}
                    </span>
                    {model.id === item.id && <Icon name="check" />}
                  </button>
                  <button type="button" className="chat-model-pin"
                    aria-label={`${favorites.includes(item.id) ? 'Открепить' : 'Закрепить'} модель ${item.label}`}
                    aria-pressed={favorites.includes(item.id)}
                    onClick={() => toggleFavorite(item.id)}>{favorites.includes(item.id) ? '★' : '☆'}</button>
                </div>
              })}
            </section>)}
          {visible.length === 0 && <div className="chat-model-empty">Модели не найдены.</div>}
        </div>
      </details>
      {catalogError && <p className="chat-model-empty" role="status">{catalogError}</p>}
      <p className="chat-model-empty">Списание с Credits пока не подключено. При собственном ключе провайдер может взимать плату отдельно.</p>
    </div>}
  </>
}
