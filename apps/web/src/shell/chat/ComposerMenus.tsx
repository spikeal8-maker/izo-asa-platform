import type { RefObject } from 'react'
import { Icon } from '../../shared/ui/Icon'
import { tools, type ChatModel, type Tool } from './modelCatalog'
import { menuKeyboard } from './composerLayout'

export function ComposerMenus({
  toolsOpen, modelOpen, tool, models, selectedModelId,
  plusButton, modelButton, inputRef,
  onCloseTools, onCloseModels, onSelectTool, onSelectModel,
}: {
  toolsOpen: boolean
  modelOpen: boolean
  tool: Tool | null
  models: ChatModel[]
  selectedModelId: string | null
  plusButton: RefObject<HTMLButtonElement | null>
  modelButton: RefObject<HTMLButtonElement | null>
  inputRef: RefObject<HTMLInputElement | null>
  onCloseTools: () => void
  onCloseModels: () => void
  onSelectTool: (tool: Tool) => void
  onSelectModel: (modelId: string) => void
}) {
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
      {models.map(item => <button type="button" role="menuitemradio"
        aria-checked={selectedModelId === item.id}
        className={selectedModelId === item.id ? 'selected' : ''}
        key={item.id} onClick={() => onSelectModel(item.id)}>
        <span className="chat-model-option">
          <strong>{item.label}</strong>
          <small>{item.description}</small>
        </span>
        {selectedModelId === item.id && <Icon name="check" />}
      </button>)}
    </div>}
  </>
}
