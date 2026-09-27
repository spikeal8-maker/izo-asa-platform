import type { RefObject } from 'react'
import { Icon } from '../../shared/ui/Icon'
import { menuKeyboard } from './composerLayout'
import { autoModel, modelCategories, type ChatModel } from './modelCatalog'

function rubles(kopeks: number | null | undefined) {
  if (kopeks == null) return 'Цена не задана'
  if (kopeks === 0) return '0 ₽'
  return `${(kopeks / 100).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`
}

function displayPrice(model: ChatModel) {
  if (model.category === 'text') return `Вход ${rubles(model.price?.input_kopeks_per_million)} · выход ${rubles(model.price?.output_kopeks_per_million)} за 1 млн токенов`
  if (model.category === 'image') return `${rubles(model.price?.image_kopeks_per_image)} за изображение`
  return 'Цена не задана'
}

export function ModelPicker({ open, model, models, defaultModelId, busy, buttonRef,
  onToggle, onClose, onSelect }: {
  open: boolean
  model: ChatModel
  models: ChatModel[]
  defaultModelId: string | undefined
  busy: boolean
  buttonRef: RefObject<HTMLButtonElement | null>
  onToggle: () => void
  onClose: () => void
  onSelect: (value: ChatModel) => void
}) {
  const defaultModel = models.find(item => item.id === defaultModelId)
  return <>
    <button ref={buttonRef} type="button" className="chat-model-selector"
      data-composer-control="compact" aria-label="Выбрать модель" aria-expanded={open}
      disabled={busy} onClick={onToggle}>
      <span>{model.label}</span><Icon name="chevron" />
    </button>
    {open && <div className="chat-popover chat-model-menu" role="menu" aria-label="Модели"
      onKeyDown={event => menuKeyboard(event, onClose, buttonRef.current)}>
      <button type="button" className={model.id === 'auto' ? 'selected model-auto' : 'model-auto'}
        role="menuitemradio" aria-checked={model.id === 'auto'} onClick={() => onSelect(autoModel)}>
        <span>Авто{defaultModel && ` · ${defaultModel.label}`}<br />
          <small>Отображаемая цена: {defaultModel ? displayPrice(defaultModel) : 'Цена не задана'}</small></span>
        {model.id === 'auto' && <Icon name="check" />}
      </button>
      {modelCategories.map(category => {
        const entries = models.filter(item => item.category === category.id)
        return <details className="chat-model-category" key={category.id}>
          <summary role="menuitem" tabIndex={0}>
            <span><Icon name={category.icon} />{category.label}</span><span>{entries.length}</span>
          </summary>
          <div className="chat-model-category-list">
            {entries.length ? entries.map(item => <button type="button" role="menuitemradio"
              aria-checked={model.id === item.id} className={model.id === item.id ? 'selected' : ''}
              key={item.id} onClick={() => onSelect(item)}>
              <span>{item.label}<br /><small>Отображаемая цена: {displayPrice(item)}</small></span>
              {model.id === item.id && <Icon name="check" />}
            </button>) : <div className="chat-model-empty">Нет опубликованных моделей</div>}
          </div>
        </details>
      })}
      <p className="chat-model-empty">Списание с Credits пока не подключено. При собственном ключе провайдер может взимать плату отдельно.</p>
    </div>}
  </>
}
