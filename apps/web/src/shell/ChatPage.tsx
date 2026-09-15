import { useRef, useState, type FormEvent } from 'react'
import { Icon, type IconName } from '../shared/ui/Icon'
import { Link } from './router'
import './chat.css'

type LocalTurn = { id: number; text: string }

const tools: { href: string; label: string; icon: IconName; detail: string }[] = [
  { href: '/image', label: 'Изображение', icon: 'image', detail: 'Создать или отредактировать изображение' },
  { href: '/studio/video', label: 'Видео', icon: 'video', detail: 'Оживить изображение или собрать сцену' },
  { href: '/studio/audio', label: 'Звук', icon: 'audio', detail: 'Озвучка, музыка и работа с голосом' },
  { href: '/studio/3d', label: '3D', icon: 'cube', detail: 'Создание и подготовка 3D-объектов' },
]

export function ChatPage() {
  const [draft, setDraft] = useState('')
  const [turns, setTurns] = useState<LocalTurn[]>([])
  const [toolsOpen, setToolsOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const textarea = useRef<HTMLTextAreaElement>(null)

  function resize() {
    const element = textarea.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return
    setTurns(current => [...current, { id: Date.now(), text }])
    setDraft('')
    setToolsOpen(false)
    setNotice('Текстовый помощник пока не подключён к серверу. Изображения уже доступны через режим «Изображение».')
    requestAnimationFrame(() => {
      if (textarea.current) textarea.current.style.height = 'auto'
    })
  }

  const empty = turns.length === 0
  return <section className={`chat-page ${empty ? 'is-empty' : ''}`} aria-label="Чат ИЗО АСА">
    <div className="chat-scroll" aria-live="polite">
      <div className="chat-column">
        {empty ? <div className="chat-empty"><h1>Чем я могу помочь?</h1></div> : <div className="chat-turns">
          {turns.map(turn => <div className="chat-turn chat-turn-user" key={turn.id}>
            <div className="chat-user-bubble">{turn.text}</div>
          </div>)}
          {notice && <div className="chat-runtime-note" role="status"><Icon name="info" /><span>{notice}</span></div>}
        </div>}
      </div>
    </div>

    <div className="chat-composer-dock">
      <div className="chat-composer-wrap">
        <form className="chat-composer" onSubmit={submit}>
          <textarea ref={textarea} rows={1} value={draft} aria-label="Сообщение"
            placeholder="Спросите что-нибудь" onChange={event => { setDraft(event.target.value); resize() }}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }} />
          <div className="chat-composer-bottom">
            <div className="chat-composer-left">
              <button type="button" className="chat-circle-button" aria-label="Добавить" aria-expanded={toolsOpen}
                onClick={() => setToolsOpen(value => !value)}><Icon name="plus" /></button>
              <button type="button" className="chat-tools-button" aria-expanded={toolsOpen}
                onClick={() => setToolsOpen(value => !value)}><Icon name="spark" /><span>Инструменты</span></button>
            </div>
            <div className="chat-composer-right">
              <button type="button" className="chat-circle-button" aria-label="Голосовой ввод" disabled title="Голосовой ввод будет подключён отдельно"><Icon name="audio" /></button>
              <button type="submit" className="chat-send-button" aria-label="Отправить" disabled={!draft.trim()}><Icon name="arrow" /></button>
            </div>
          </div>
          {toolsOpen && <div className="chat-tools-popover" role="menu" aria-label="Инструменты">
            {tools.map(tool => <Link key={tool.href} href={tool.href} role="menuitem" className="chat-tool-item">
              <Icon name={tool.icon} /><span><strong>{tool.label}</strong><small>{tool.detail}</small></span>
            </Link>)}
          </div>}
        </form>
        <div className="chat-composer-note">ИЗО АСА может ошибаться. Проверяйте важную информацию.</div>
      </div>
    </div>
  </section>
}
