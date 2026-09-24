import type { ChatPolicyView } from '../../shared/api'
import type { IconName } from '../../shared/ui/Icon'

export type ChatModel = ChatPolicyView['models'][number]
export type Tool = 'image' | 'video' | 'audio' | '3d' | 'web'

export const tools: { id: Tool; label: string; icon: IconName }[] = [
  { id: 'image', label: 'Создать изображение', icon: 'image' },
  { id: 'video', label: 'Создать видео', icon: 'video' },
  { id: 'audio', label: 'Создать звук', icon: 'audio' },
  { id: '3d', label: 'Создать 3D', icon: 'cube' },
  { id: 'web', label: 'Поиск в интернете', icon: 'globe' },
]

export const toolById = Object.fromEntries(
  tools.map(item => [item.id, item]),
) as Record<Tool, (typeof tools)[number]>

export function textModels(policy: ChatPolicyView | null): ChatModel[] {
  return policy?.models ?? []
}
