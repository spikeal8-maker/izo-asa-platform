import { isValidElement, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import { PrivateImage } from '../../features/gallery/PrivateImage'
import type { AuthView, ChatAttachmentView, MessageView as Message } from '../../shared/api'
import type { Asset } from '../../shared/workspace-api'

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

function ChatAttachment({ attachment, auth }: {
  attachment: ChatAttachmentView
  auth: AuthView
}) {
  const asset: Asset = {
    id: attachment.asset_id,
    kind: 'image',
    content_type: 'image/png',
    byte_size: attachment.byte_size,
    width: attachment.width,
    height: attachment.height,
    sha256: attachment.sha256,
    created_at: attachment.created_at,
  }
  return <div className="chat-message-image">
    <PrivateImage asset={asset} auth={auth} />
  </div>
}

export function ChatMessage({ message, auth }: { message: Message; auth: AuthView }) {
  if (message.role === 'user') {
    return <div className="chat-turn chat-turn-user" data-message-id={message.id}>
      <div className="chat-user-bubble">
        {(message.attachments?.length ?? 0) > 0 && <div className="chat-message-attachments">
          {message.attachments?.map(attachment =>
            <ChatAttachment key={attachment.id} attachment={attachment} auth={auth} />)}
        </div>}
        <div className="chat-user-text">{message.content}</div>
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
