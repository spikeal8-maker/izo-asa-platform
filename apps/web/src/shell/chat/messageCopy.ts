import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'

type CopyNode = {
  type: string
  value?: string
  alt?: string
  checked?: boolean | null
  ordered?: boolean
  start?: number | null
  children?: CopyNode[]
}

function inline(node: CopyNode): string {
  if (node.type === 'html') return ''
  if (node.type === 'break') return '\n'
  if (node.type === 'image' || node.type === 'imageReference') return node.alt || ''
  if (node.value !== undefined) return node.value
  return (node.children || []).map(inline).join('')
}

function block(node: CopyNode, depth = 0): string {
  if (node.type === 'html' || node.type === 'definition') return ''
  if (node.type === 'code') return node.value || ''
  if (node.type === 'thematicBreak') return '---'
  if (node.type === 'table') return (node.children || []).map(row =>
    (row.children || []).map(inline).join('\t')).join('\n')
  if (node.type === 'list') return (node.children || []).map((item, index) => {
    const marker = node.ordered ? `${(node.start ?? 1) + index}. ` : '- '
    const task = item.checked === null || item.checked === undefined ? '' : item.checked ? '[x] ' : '[ ] '
    const parts = (item.children || []).map(child => block(child, depth + 1)).filter(Boolean)
    const first = parts.shift() || ''
    return `${'  '.repeat(depth)}${marker}${task}${first}${parts.map(part => `\n${part}`).join('')}`
  }).join('\n')
  if (node.type === 'listItem') return (node.children || []).map(child => block(child, depth)).filter(Boolean).join('\n')
  if (node.type === 'root' || node.type === 'blockquote') {
    return (node.children || []).map(child => block(child, depth)).filter(Boolean).join('\n\n')
  }
  return inline(node)
}

// Parse the saved message model; never copy rendered DOM controls or toolbar labels.
export function plainMessageText(markdown: string): string {
  return block(unified().use(remarkParse).use(remarkGfm).parse(markdown) as CopyNode).trim()
}
