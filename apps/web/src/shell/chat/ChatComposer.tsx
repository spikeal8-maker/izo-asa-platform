import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiRequest, type AuthView } from '../../shared/api'
import type { Plan } from '../../shared/workspace-api'
import { Icon, type IconName } from '../../shared/ui/Icon'
import { autoModel, configuredModels, modelCategories, type ChatModel } from './modelCatalog'
import { menuKeyboard, useComposerLayout } from './composerLayout'
import { useVoiceCapture } from './useVoiceCapture'
import './ChatComposer.css'

type Tool = 'image' | 'video' | 'audio' | '3d' | 'web'
const tools: { id: Tool; label: string; icon: IconName }[] = [
{ id: 'image', label: 'Создать изображение', icon: 'image' },
{ id: 'video', label: 'Создать видео', icon: 'video' },
{ id: 'audio', label: 'Создать звук', icon: 'audio' },
{ id: '3d', label: 'Создать 3D', icon: 'cube' },
{ id: 'web', label: 'Поиск в интернете', icon: 'globe' },
]
const toolById = Object.fromEntries(tools.map(item => [item.id, item])) as Record<Tool, (typeof tools)[number]>

export function ChatComposer({ auth, onSend }: {
auth: AuthView | null | undefined
onSend: (text: string) => void
}) {
const [draft, setDraft] = useState('')
const [toolsOpen, setToolsOpen] = useState(false)
const [modelOpen, setModelOpen] = useState(false)
const [model, setModel] = useState<ChatModel>(autoModel)
const [models, setModels] = useState<ChatModel[]>([])
const [tool, setTool] = useState<Tool | null>(null)
const [attachment, setAttachment] = useState<File | null>(null)
const fileInput = useRef<HTMLInputElement>(null)
const plusButton = useRef<HTMLButtonElement>(null)
const modelButton = useRef<HTMLButtonElement>(null)
const voice = useVoiceCapture()
const forcedExpanded = voice.active || Boolean(tool) || Boolean(attachment)
const layout = useComposerLayout(draft, forcedExpanded)

useEffect(() => {
setModels([])
if (!auth) return
const controller = new AbortController()
apiRequest<Plan>('/api/v1/entitlements', { signal: controller.signal })
.then(value => setModels(configuredModels(value)))
.catch(() => setModels([]))
return () => controller.abort()
}, [auth?.account.id])

useEffect(() => {
const dismiss = (event: PointerEvent) => {
const target = event.target
if (!(target instanceof Element)) return
if (modelOpen && !target.closest('.chat-model-selector,.chat-model-menu')) setModelOpen(false)
if (toolsOpen && !target.closest('.chat-tools-menu,button[aria-label="Добавить"]')) setToolsOpen(false)
}
document.addEventListener('pointerdown', dismiss)
return () => document.removeEventListener('pointerdown', dismiss)
}, [modelOpen, toolsOpen])

useEffect(() => {
if (!modelOpen && !toolsOpen) return
const escape = (event: globalThis.KeyboardEvent) => {
if (event.key !== 'Escape') return
event.preventDefault()
if (modelOpen) {
setModelOpen(false)
requestAnimationFrame(() => modelButton.current?.focus())
}
if (toolsOpen) {
setToolsOpen(false)
requestAnimationFrame(() => plusButton.current?.focus())
}
}
document.addEventListener('keydown', escape)
return () => document.removeEventListener('keydown', escape)
}, [modelOpen, toolsOpen])

function submit(event: FormEvent) {
event.preventDefault()
const text = draft.trim()
if (!text || voice.active) return
onSend(text)
setDraft('')
requestAnimationFrame(() => layout.textareaRef.current?.focus())
}

function selectTool(next: Tool) {
setTool(next)
setToolsOpen(false)
setModelOpen(false)
}

function selectModel(next: ChatModel) {
setModel(next)
setModelOpen(false)
requestAnimationFrame(() => modelButton.current?.focus())
}

return <div className="chat-composer-wrap">
<form ref={layout.formRef}
className={`chat-composer ${layout.expanded ? 'is-expanded' : 'is-compact'} ${voice.active ? 'voice-active' : ''}`}
data-layout={layout.expanded ? 'expanded' : 'compact'} onSubmit={submit}
onKeyDown={event => {
if (event.key !== 'Escape') return
if (modelOpen) {
event.preventDefault(); setModelOpen(false)
requestAnimationFrame(() => modelButton.current?.focus())
}
if (toolsOpen) {
event.preventDefault(); setToolsOpen(false)
requestAnimationFrame(() => plusButton.current?.focus())
}
}}>
<div ref={layout.measureRef} className="chat-composer-measure" aria-hidden="true" />
{voice.active
? <div className="chat-voice-capture" role="status" aria-label="Микрофон активен">
<span className="chat-voice-label">Слушаю</span>
<div ref={voice.waveformRef} className="chat-voice-waveform" aria-hidden="true">
{Array.from({ length: voice.barCount }, (_, index) => <span key={index} style={{ transform: 'scaleY(0.08)' }} />)}
</div>
</div>
: <textarea ref={layout.textareaRef} rows={1} value={draft} aria-label="Сообщение" placeholder="Спросите что-нибудь"
onChange={event => setDraft(event.target.value)}
onKeyDown={event => {
if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
event.preventDefault(); event.currentTarget.form?.requestSubmit()
}
}} />}
<input ref={fileInput} className="chat-file-input" type="file" aria-label="Выбрать файл"
onChange={event => setAttachment(event.currentTarget.files?.[0] ?? null)} />

<button ref={plusButton} type="button" className="chat-circle-button chat-composer-plus" data-composer-control="compact"
aria-label="Добавить" aria-expanded={toolsOpen}
onClick={() => { setToolsOpen(value => !value); setModelOpen(false) }}><Icon name="plus" /></button>

{(tool || attachment) && <div className="chat-composer-state">
{tool && <button type="button" className="chat-state-chip selected" aria-label={`Убрать инструмент: ${toolById[tool].label}`}
onClick={() => setTool(null)}><Icon name={toolById[tool].icon} /><span>{toolById[tool].label}</span><Icon name="close" /></button>}
{attachment && <span className="chat-state-chip attachment-chip"><Icon name="file" /><span>{attachment.name}</span>
<button type="button" aria-label="Удалить вложение" onClick={() => {
setAttachment(null); if (fileInput.current) fileInput.current.value = ''
}}><Icon name="close" /></button>
</span>}
</div>}

<button ref={modelButton} type="button" className="chat-model-selector" data-composer-control="compact"
aria-label="Выбрать модель" aria-expanded={modelOpen}
onClick={() => { setModelOpen(value => !value); setToolsOpen(false) }}>
<span>{model.label}</span><Icon name="chevron" />
</button>
<button type="button" className={`chat-circle-button chat-mic-button ${voice.active ? 'active' : ''}`}
data-composer-control="compact" aria-label={voice.active ? 'Остановить микрофон' : 'Микрофон'}
onClick={() => voice.active ? voice.stop() : void voice.start()}><Icon name="mic" /></button>
<button type="submit" className="chat-send-button" data-composer-control="compact" aria-label="Отправить"
disabled={!draft.trim() || voice.active}><Icon name="send" /></button>

{voice.error && <div className="chat-voice-error" role="alert">{voice.error}</div>}
{toolsOpen && <div className="chat-popover chat-tools-menu" role="menu" aria-label="Инструменты"
onKeyDown={event => menuKeyboard(event, () => setToolsOpen(false), plusButton.current)}>
<button type="button" role="menuitem" onClick={() => { setToolsOpen(false); fileInput.current?.click() }}>
<Icon name="file" /><span>Добавить файл</span>
</button>
{tools.map(item => <button type="button" role="menuitem" key={item.id}
className={tool === item.id ? 'selected' : ''} aria-pressed={tool === item.id}
onClick={() => selectTool(item.id)}><Icon name={item.icon} /><span>{item.label}</span></button>)}
</div>}
{modelOpen && <div className="chat-popover chat-model-menu" role="menu" aria-label="Модели"
onKeyDown={event => menuKeyboard(event, () => setModelOpen(false), modelButton.current)}>
<button type="button" className={model.id === 'auto' ? 'selected model-auto' : 'model-auto'}
role="menuitemradio" aria-checked={model.id === 'auto'} onClick={() => selectModel(autoModel)}>
<span>Авто</span>{model.id === 'auto' && <Icon name="check" />}
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
key={item.id} onClick={() => selectModel(item)}>
<span>{item.label}</span>{model.id === item.id && <Icon name="check" />}
</button>) : <div className="chat-model-empty">Нет опубликованных моделей</div>}
</div>
</details>
})}
</div>}
</form>
<div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
</div>
}
