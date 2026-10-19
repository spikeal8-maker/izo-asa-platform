import { isValidElement, useEffect, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './ChatRenderer.css'
import type { AuthView, MessageView as Message } from '../../shared/api'
import { usePrivateImageUrl } from '../../shared/usePrivateImageUrl'
import { plainMessageText } from './messageCopy'
import type { AttemptControls } from './useAssistantAttempts'

type Attachment = NonNullable<Message['attachments']>[number]

function ChatImage({ attachment, auth }: { attachment: Attachment; auth: AuthView }) {
  const { url, error, retry } = usePrivateImageUrl({ ...attachment, id: attachment.asset_id }, auth)
  return <div className="chat-message-image">
    {url ? <img src={url} alt="Прикреплённое изображение" width={attachment.width} height={attachment.height} />
      : error ? <div role="alert">Не удалось открыть изображение. <button onClick={retry}>Повторить</button></div>
      : <span role="status">Загружаем изображение…</span>}
  </div>
}

function textOf(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children)
  return ''
}

function safeLink(href?: string): { href: string; external: boolean } | null {
  if (!href) return null
  try {
    const url = new URL(href, window.location.origin)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null
    return { href, external: url.origin !== window.location.origin }
  } catch {
    return null
  }
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, setCopied] = useState(false)
  const exact = textOf(children).replace(/\n$/, '')

  async function copy() {
    try {
      await navigator.clipboard.writeText(exact)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch {
      setCopied(false)
    }
  }
  return <div className="chat-code-block">
    <div className="chat-code-toolbar">
      <button type="button" onClick={() => void copy()}>
        {copied ? 'Скопировано' : 'Копировать'}
      </button>
    </div>
    <pre>{children}</pre>
  </div>
}

function AttemptActions({ controls }: { controls: AttemptControls }) {
  const { turn, blocked, saving, uncertain, feedback, regenerate, select } = controls
  if (!turn.selected_attempt) return null
  const latest = turn.latest_attempt?.id !== turn.selected_attempt_id ? turn.latest_attempt : null
  const status = latest?.error_code === 'provider_outcome_unknown' ? 'Результат нового запроса уточняется. Предыдущий ответ сохранён.'
    : latest?.state === 'pending' || latest?.state === 'streaming' ? 'Готовим новый вариант…'
    : latest?.state === 'stopped' ? 'Новый вариант остановлен. Предыдущий ответ сохранён.'
    : latest && ['error', 'interrupted'].includes(latest.state) ? 'Новый вариант не получен. Предыдущий ответ сохранён.' : ''
  const canRegenerate = !blocked && turn.selected_attempt?.state === 'completed'
  return <div className="chat-attempt-actions" role="group" aria-label="Варианты ответа">
    <button type="button" aria-disabled={!canRegenerate} onClick={() => { if (canRegenerate) regenerate() }}>
      {uncertain ? 'Проверить запрос' : 'Ответить заново'}
    </button>
    {turn.completed_count > 1 && <div className="chat-attempt-selector">
      <button type="button" aria-label="Предыдущий вариант" aria-disabled={saving || !turn.previous_completed_attempt_id}
        onClick={() => { if (!saving && turn.previous_completed_attempt_id) select(turn.previous_completed_attempt_id) }}>‹</button>
      <span aria-live="polite">{turn.selected_completed_position} из {turn.completed_count}</span>
      <button type="button" aria-label="Следующий вариант" aria-disabled={saving || !turn.next_completed_attempt_id}
        onClick={() => { if (!saving && turn.next_completed_attempt_id) select(turn.next_completed_attempt_id) }}>›</button>
    </div>}
    {status && <span role="status">{status}</span>}
    {feedback && <span className="chat-attempt-feedback" role="status">{feedback}</span>}
  </div>
}

function MessageActions({ content, assistant, attempts }: { content: string; assistant: boolean; attempts?: AttemptControls }) {
  const [feedback, setFeedback] = useState('')
  useEffect(() => { setFeedback('') }, [content])

  async function copy(markdown: boolean) {
    try {
      await navigator.clipboard.writeText(markdown ? content : assistant ? plainMessageText(content) : content)
      setFeedback(markdown ? 'Markdown скопирован' : 'Скопировано')
    } catch {
      setFeedback('Не удалось скопировать. Проверьте доступ к буферу обмена.')
    }
  }

  return <div className="chat-message-actions">
    <button type="button" disabled={!content} onClick={() => void copy(false)}>Копировать</button>
    {assistant && <button type="button" disabled={!content} onClick={() => void copy(true)}>Копировать Markdown</button>}
    {attempts && <AttemptActions controls={attempts} />}
    <span role="status" aria-live="polite">{feedback}</span>
  </div>
}

export function ChatMessage({ message, auth, attempts }: {
  message: Message; auth: AuthView | null | undefined; attempts?: AttemptControls
}) {
  if (message.role === 'user') {
    return <div className="chat-turn chat-turn-user" data-message-id={message.id}>
      <div className="chat-user-bubble">
        {message.attachments?.length && auth ? <div className="chat-message-images">
          {message.attachments.map(attachment => <ChatImage key={attachment.id} attachment={attachment} auth={auth} />)}
        </div> : null}
        {message.content && <div>{message.content}</div>}
      </div>
      <MessageActions content={message.content} assistant={false} />
    </div>
  }

  return <div className="chat-turn chat-turn-assistant" data-message-id={message.id} data-turn-id={attempts?.turn.id}>
    <div className="chat-assistant-message">
      <ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={{
        a: ({ href, children }) => {
          const link = safeLink(href)
          return link
            ? <a href={link.href} target={link.external ? '_blank' : undefined}
                rel={link.external ? 'noreferrer noopener' : undefined}>{children}</a>
            : <span>{children}</span>
        },
        pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
        table: ({ children }) => <div className="chat-table-scroll" role="region" aria-label="Таблица ответа" tabIndex={0}>
          <table>{children}</table>
        </div>,
        img: ({ alt }) => <span>{alt || 'Изображение в ответе недоступно'}</span>,
      }}>{message.content || (message.state === 'partial' ? '…' : '')}</ReactMarkdown>
      {message.state !== 'complete' && message.state !== 'partial'
        && <div className="chat-message-state" role="status">
          {message.state === 'stopped' ? 'Ответ остановлен.'
            : message.state === 'interrupted' ? 'Ответ прерван.'
            : 'Ответ завершился с ошибкой.'}
        </div>}
    </div>
    <MessageActions content={message.content} assistant attempts={attempts} />
  </div>
}
