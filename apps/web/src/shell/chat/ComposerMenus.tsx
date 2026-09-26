import { useEffect, useState, type RefObject } from 'react'
import type { CredentialView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import {
  groupedTextModels, modelAvailable, modelMeta, modelSearchText, tools,
  type ChatModel, type Tool,
} from './modelCatalog'
import { menuKeyboard } from './composerLayout'

export function ComposerMenus({
  toolsOpen, modelOpen, tool, models, credentials, selectedModelId,
  plusButton, modelButton, inputRef,
  onCloseTools, onCloseModels, onSelectTool, onSelectModel,
}: {
  toolsOpen: boolean
  modelOpen: boolean
  tool: Tool | null
  models: ChatModel[]
  credentials: CredentialView[]
  selectedModelId: string | null
  plusButton: RefObject<HTMLButtonElement | null>
  modelButton: RefObject<HTMLButtonElement | null>
  inputRef: RefObject<HTMLInputElement | null>
  onCloseTools: () => void
  onCloseModels: () => void
  onSelectTool: (tool: Tool) => void
  onSelectModel: (modelId: string) => void
}) {
  const [query, setQuery] = useState('')
  useEffect(() => {
    if (!modelOpen) setQuery('')
  }, [modelOpen])
  const normalized = query.trim().toLocaleLowerCase('ru')
  const visible = normalized
    ? models.filter(item => modelSearchText(item).includes(normalized))
    : models

  return <>
    {toolsOpen && <div className="chat-popover chat-tools-menu" role="menu" aria-label="Инструменты"
      onKeyDown={event => menuKeyboard(event, onCloseTools, plusButton.current)}>
      <button type="button" role="menuitem" onClick={() => {
        onCloseTools()
        inputRef.current?.click()
      }}><Icon name="image" /><span>Изображение</span></button>
      {tools.map(item => <button type="button" role="menuitem" key={item.id}
        className={tool === item.id ? 'selected' : ''} aria-pressed={tool === item.id}
        onClick={() => onSelectTool(item.id)}>
        <Icon name={item.icon} /><span>{item.label}</span>
      </button>)}
    </div>}
    {modelOpen && <div className="chat-popover chat-model-menu" role="menu" aria-label="Модели"
      onKeyDown={event => menuKeyboard(event, onCloseModels, modelButton.current)}>
      <label className="chat-model-search">
        <Icon name="search" />
        <input value={query} onChange={event => setQuery(event.target.value)}
          placeholder="Поиск модели" aria-label="Поиск модели" />
      </label>
      {groupedTextModels(visible).map(group =>
        <section className="chat-model-provider" key={group.provider} aria-label={group.label}>
          <div className="chat-model-provider-title">{group.label}</div>
          {group.models.map(item => {
            const available = modelAvailable(item, credentials)
            return <button type="button" role="menuitemradio"
              aria-checked={selectedModelId === item.id}
              aria-disabled={!available}
              disabled={!available}
              className={selectedModelId === item.id ? 'selected' : ''}
              key={item.id} onClick={() => onSelectModel(item.id)}>
              <span className="chat-model-option">
                <strong>{item.label}</strong>
                <small>{modelMeta(item)}</small>
                <small>{available
                  ? item.description
                  : `Подключите ${group.label} API key`}</small>
              </span>
              {selectedModelId === item.id && <Icon name="check" />}
            </button>
          })}
        </section>)}
    </div>}
  </>
}
