import { isValidElement, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import type { AuthView, MessageView as Message } from '../../shared/api'
import { usePrivateImageUrl } from '../../shared/usePrivateImageUrl'

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

export function ChatMessage({ message, auth }: { message: Message; auth: AuthView | null | undefined }) {
  if (message.role === 'user') {
    return <div className="chat-turn chat-turn-user" data-message-id={message.id}>
      <div className="chat-user-bubble">
        {message.attachments?.length && auth ? <div className="chat-message-images">
          {message.attachments.map(attachment => <ChatImage key={attachment.id} attachment={attachment} auth={auth} />)}
        </div> : null}
        {message.content && <div>{message.content}</div>}
      </div>
    </div>
  }

  return <div className="chat-turn chat-turn-assistant" data-message-id={message.id}>
    <div className="chat-assistant-message">
      <ReactMarkdown skipHtml components={{
        a: ({ href, children }) => {
          const link = safeLink(href)
          return link
            ? <a href={link.href} target={link.external ? '_blank' : undefined}
                rel={link.external ? 'noreferrer noopener' : undefined}>{children}</a>
            : <span>{children}</span>
        },
        pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
        img: ({ alt }) => <span>{alt || 'Изображение в ответе недоступно'}</span>,
      }}>{message.content || (message.state === 'partial' ? '…' : '')}</ReactMarkdown>
      {message.state !== 'complete' && message.state !== 'partial'
        && <div className="chat-message-state" role="status">
          {message.state === 'stopped' ? 'Ответ остановлен.'
            : message.state === 'interrupted' ? 'Ответ прерван.'
            : 'Ответ завершился с ошибкой.'}
        </div>}
    </div>
  </div>
}
