import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiRequest, type AuthView, type ChatPolicyView } from '../../shared/api'
import { Icon } from '../../shared/ui/Icon'
import {
autoModel, textModels, toolById, tools,
type ChatModel, type Tool,
} from './modelCatalog'
import { menuKeyboard, useComposerLayout } from './composerLayout'
import { ModelPicker } from './ModelPicker'
import { useVoiceCapture } from './useVoiceCapture'
import './ChatComposer.css'
export function ChatComposer({ auth, policy, busy, stoppable, disabled,
onSend, onStop, onUnsupported }: {
auth: AuthView | null | undefined
policy: ChatPolicyView | null
busy: boolean
stoppable: boolean
disabled: boolean
onSend: (text: string, modelId: string) => Promise<boolean>
onStop: () => void
onUnsupported: () => void
}) {
const [draft, setDraft] = useState('')
const [toolsOpen, setToolsOpen] = useState(false)
const [modelOpen, setModelOpen] = useState(false)
const [model, setModel] = useState<ChatModel>(autoModel)
const [modelError, setModelError] = useState('')
const [checkingPrice, setCheckingPrice] = useState(false)
const [tool, setTool] = useState<Tool | null>(null)
const [attachment, setAttachment] = useState<File | null>(null)
const fileInput = useRef<HTMLInputElement>(null)
const plusButton = useRef<HTMLButtonElement>(null)
const modelButton = useRef<HTMLButtonElement>(null)
const preflight = useRef<AbortController | null>(null)
const voice = useVoiceCapture()
const forcedExpanded = voice.active || Boolean(tool) || Boolean(attachment)
const layout = useComposerLayout(draft, forcedExpanded)
const models = auth ? textModels(policy) : []
useEffect(() => () => preflight.current?.abort(), [])
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
async function submit(event: FormEvent) {
event.preventDefault()
const text = draft.trim()
if (!text || voice.active || busy || disabled || preflight.current) return
const modelId = model.id === 'auto'
? policy?.default_model
: model.category === 'text' ? model.id : null
if (!modelId || tool || attachment) {
onUnsupported()
return
}
if (!policy?.models.some(item => item.id === modelId)) {
setModelError('Выбранная модель больше недоступна. Выберите другую модель или обновите страницу.')
return
}
const controller = new AbortController()
preflight.current = controller; setCheckingPrice(true)
setModelOpen(false); setToolsOpen(false)
try {
let latest: ChatPolicyView
try { latest = await apiRequest<ChatPolicyView>('/api/v1/chat/policy', {
signal: controller.signal, timeoutMs: 6000,
}) } catch {
if (!controller.signal.aborted) setModelError('Не удалось проверить цену. Повторите попытку позднее.')
return
}
if (controller.signal.aborted) return
if (latest.revision !== policy.revision || !latest.models.some(item => item.id === modelId)) {
setModelError('Модели или цены изменились — обновите чат перед отправкой.')
return
}
setModelError('')
if (!await onSend(text, modelId)) return
setDraft('')
requestAnimationFrame(() => layout.textareaRef.current?.focus())
} finally {
if (preflight.current === controller) preflight.current = null
if (!controller.signal.aborted) setCheckingPrice(false)
}
}
function selectTool(next: Tool) {
if (preflight.current) return
setTool(next); setToolsOpen(false); setModelOpen(false)
}
function selectModel(next: ChatModel) {
if (preflight.current) return
setModel(next); setModelError(''); setModelOpen(false)
requestAnimationFrame(() => modelButton.current?.focus())
}
return <div className="chat-composer-wrap">
<form ref={layout.formRef}
className={`chat-composer ${layout.expanded ? 'is-expanded' : 'is-compact'} ${voice.active ? 'voice-active' : ''}`}
data-layout={layout.expanded ? 'expanded' : 'compact'} onSubmit={event => void submit(event)}
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
{Array.from({ length: voice.barCount }, (_, index) =>
<span key={index} style={{ transform: 'scaleY(0.08)' }} />)}
</div>
</div>
: <textarea ref={layout.textareaRef} rows={1} value={draft} aria-label="Сообщение"
placeholder={disabled ? 'Подключите ключ DeepSeek' : 'Спросите что-нибудь'}
disabled={disabled || busy || checkingPrice}
onChange={event => { if (!preflight.current) setDraft(event.target.value) }}
onKeyDown={event => {
if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
event.preventDefault(); event.currentTarget.form?.requestSubmit()
}
}} />}
<input ref={fileInput} className="chat-file-input" type="file" aria-label="Выбрать файл"
disabled={checkingPrice} onChange={event => { if (!preflight.current) setAttachment(event.currentTarget.files?.[0] ?? null) }} />
<button ref={plusButton} type="button" className="chat-circle-button chat-composer-plus"
data-composer-control="compact" aria-label="Добавить" aria-expanded={toolsOpen}
disabled={busy || checkingPrice}
onClick={() => { setToolsOpen(value => !value); setModelOpen(false) }}>
<Icon name="plus" />
</button>
{(tool || attachment) && <div className="chat-composer-state">
{tool && <button type="button" className="chat-state-chip selected"
aria-label={`Убрать инструмент: ${toolById[tool].label}`}
disabled={checkingPrice} onClick={() => setTool(null)}>
<Icon name={toolById[tool].icon} /><span>{toolById[tool].label}</span><Icon name="close" />
</button>}
{attachment && <span className="chat-state-chip attachment-chip">
<Icon name="file" /><span>{attachment.name}</span>
<button type="button" aria-label="Удалить вложение" disabled={checkingPrice} onClick={() => {
setAttachment(null); if (fileInput.current) fileInput.current.value = ''
}}><Icon name="close" /></button>
</span>}
</div>}
<ModelPicker open={modelOpen} model={model} models={models} defaultModelId={policy?.default_model}
busy={busy || checkingPrice} buttonRef={modelButton} onToggle={() => { setModelOpen(value => !value); setToolsOpen(false) }}
onClose={() => setModelOpen(false)} onSelect={selectModel} />
<button type="button" className={`chat-circle-button chat-mic-button ${voice.active ? 'active' : ''}`}
data-composer-control="compact" aria-label={voice.active ? 'Остановить микрофон' : 'Микрофон'}
disabled={busy || checkingPrice} onClick={() => voice.active ? voice.stop() : void voice.start()}>
<Icon name="mic" />
</button>
{busy
? <button type="button" className="chat-send-button" data-composer-control="compact"
aria-label="Остановить ответ" disabled={!stoppable} onClick={onStop}><Icon name="close" /></button>
: <button type="submit" className="chat-send-button" data-composer-control="compact"
aria-label={checkingPrice ? 'Проверяем модель и цену' : 'Отправить'}
disabled={disabled || !draft.trim() || voice.active || checkingPrice}>
<Icon name="send" />
</button>}
{voice.error && <div className="chat-voice-error" role="alert">{voice.error}</div>}
{modelError && <div className="chat-voice-error" role="alert">{modelError}</div>}
{toolsOpen && <div className="chat-popover chat-tools-menu" role="menu" aria-label="Инструменты"
onKeyDown={event => menuKeyboard(event, () => setToolsOpen(false), plusButton.current)}>
<button type="button" role="menuitem" disabled={checkingPrice} onClick={() => {
setToolsOpen(false); fileInput.current?.click()
}}><Icon name="file" /><span>Добавить файл</span></button>
{tools.map(item => <button type="button" role="menuitem" key={item.id} disabled={checkingPrice}
className={tool === item.id ? 'selected' : ''} aria-pressed={tool === item.id}
onClick={() => selectTool(item.id)}>
<Icon name={item.icon} /><span>{item.label}</span>
</button>)}
</div>}
</form>
<div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
</div>
}
