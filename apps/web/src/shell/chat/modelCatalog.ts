import type { ChatPolicyView } from '../../shared/api'
import type { IconName } from '../../shared/ui/Icon'

export type ModelCategory = 'text' | 'image' | 'video' | 'audio' | '3d'
export type DisplayPrice = ChatPolicyView['models'][number]['price']
export type ChatModel = { id: string; label: string; category: ModelCategory | null; price?: DisplayPrice | null }
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

export const autoModel: ChatModel = { id: 'auto', label: 'Авто', category: null }

export const modelCategories: { id: ModelCategory; label: string; icon: IconName }[] = [
  { id: 'text', label: 'Текст', icon: 'chat' },
  { id: 'image', label: 'Изображения', icon: 'image' },
  { id: 'video', label: 'Видео', icon: 'video' },
  { id: 'audio', label: 'Звук', icon: 'audio' },
  { id: '3d', label: '3D', icon: 'cube' },
]

export function textModels(policy: ChatPolicyView | null): ChatModel[] {
  return policy?.models.map(item => ({ ...item, category: 'text' as const })) ?? []
}
